from __future__ import annotations

import atexit
import logging
import queue
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Iterable, Iterator

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from app.freeloader.browser import (
    FreeloaderBrowserSession,
    close_browser_session,
    launch_browser_session,
)
from app.freeloader.page import FreeloaderPageTargets, build_page_targets


_BROWSER_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="freeloader_browser")
_WORKER_SESSION: FreeloaderBrowserSession | None = None


def _worker_session_is_usable(session: FreeloaderBrowserSession | None) -> bool:
    if session is None:
        return False
    try:
        return session.browser.is_connected()
    except Exception:
        return False


def _reset_worker_session(logger) -> None:
    global _WORKER_SESSION
    session = _WORKER_SESSION
    _WORKER_SESSION = None
    if session is not None:
        close_browser_session(session, logger)


def _resolve_worker_page(
    session: FreeloaderBrowserSession,
    config,
    targets: FreeloaderPageTargets,
    logger,
) -> Page:
    try:
        if session.page is not None and not session.page.is_closed():
            current_url = session.page.url or ""
            if current_url.startswith(targets.chat_url) or "chatgpt.com" in current_url:
                return session.page
    except Exception:
        pass

    for page in session.context.pages:
        try:
            current_url = page.url or ""
            if current_url.startswith(targets.chat_url) or "chatgpt.com" in current_url:
                session.page = page
                return page
        except Exception:
            continue

    page = session.context.new_page()
    page.goto(config.chatgpt_url, wait_until="domcontentloaded", timeout=60000)
    session.page = page
    return page


def _ensure_worker_session(config, targets: FreeloaderPageTargets, logger) -> FreeloaderBrowserSession:
    global _WORKER_SESSION
    if _worker_session_is_usable(_WORKER_SESSION):
        _WORKER_SESSION.context.set_default_timeout(15000)
        _WORKER_SESSION.page = _resolve_worker_page(_WORKER_SESSION, config, targets, logger)
        logger.info("Reusing dedicated Freeloader browser worker session at: %s", _WORKER_SESSION.page.url)
        return _WORKER_SESSION

    _reset_worker_session(logger)
    _WORKER_SESSION = launch_browser_session(config, logger)
    _WORKER_SESSION.page = _resolve_worker_page(_WORKER_SESSION, config, targets, logger)
    return _WORKER_SESSION


def _shutdown_browser_executor() -> None:
    logger = logging.getLogger("freeloader")
    try:
        _BROWSER_EXECUTOR.submit(_reset_worker_session, logger).result(timeout=5)
    except Exception:
        pass
    try:
        _BROWSER_EXECUTOR.shutdown(wait=False, cancel_futures=True)
    except Exception:
        pass


atexit.register(_shutdown_browser_executor)


def _first_visible_locator(
    page: Page,
    selectors: Iterable[str],
    timeout_ms: int = 3000,
) -> Locator | None:
    """Return the first visible locator from a list of fallback selectors."""
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            locator.wait_for(state="visible", timeout=timeout_ms)
            return locator
        except PlaywrightTimeoutError:
            continue
    return None


def _wait_for_chat_input(
    page: Page,
    targets: FreeloaderPageTargets,
    logger,
    timeout_seconds: int = 30,
) -> Locator:
    """Wait for the ChatGPT composer and raise a helpful error if it never appears."""
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        input_locator = _first_visible_locator(page, targets.chat_input_selectors, timeout_ms=2000)
        if input_locator is not None:
            logger.info("Chat input is ready.")
            return input_locator

        logger.info("Waiting for ChatGPT input to appear.")
        time.sleep(1.0)

    raise RuntimeError(
        "ChatGPT input box is not visible. Make sure Brave is open on chatgpt.com, "
        "you are logged in, and no verification or modal is blocking the page."
    )


def _clear_prompt_box(page: Page, input_locator: Locator) -> None:
    """Clear any previous text from the chat composer."""
    input_locator.click()
    try:
        input_locator.fill("")
    except Exception:
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")


def _set_prompt_fast(input_locator: Locator, prompt: str) -> bool:
    """Try the fast direct-fill path before falling back to slow key typing."""
    try:
        input_locator.fill(prompt)
        return True
    except Exception:
        pass

    try:
        return bool(
            input_locator.evaluate(
                """
                (node, value) => {
                    const text = String(value ?? '');
                    node.focus();

                    if ('value' in node) {
                        node.value = text;
                        node.dispatchEvent(new Event('input', { bubbles: true }));
                        node.dispatchEvent(new Event('change', { bubbles: true }));
                        return true;
                    }

                    if (node.isContentEditable) {
                        node.textContent = text;
                        node.dispatchEvent(new InputEvent('input', {
                            bubbles: true,
                            data: text,
                            inputType: 'insertText',
                        }));
                        return true;
                    }

                    return false;
                }
                """,
                prompt,
            )
        )
    except Exception:
        return False


def _type_prompt(page: Page, input_locator: Locator, prompt: str, logger, delay_ms: int) -> None:
    """Paste the prompt quickly, with a typed fallback only if direct fill fails."""
    logger.info("Pasting prompt into ChatGPT.")
    if _set_prompt_fast(input_locator, prompt):
        return

    logger.info("Fast paste was unavailable, falling back to typed input.")
    for character in prompt:
        if character == "\n":
            page.keyboard.press("Shift+Enter")
        else:
            page.keyboard.type(character, delay=delay_ms)


def _submit_prompt(page: Page, input_locator: Locator, targets: FreeloaderPageTargets, logger) -> None:
    """Submit the prompt through the focused composer first, then fall back to the button."""
    try:
        input_locator.focus()
    except Exception:
        pass

    try:
        input_locator.press("Enter")
        logger.info("Prompt submitted with Enter.")
        return
    except Exception:
        logger.debug("Enter submit failed, falling back to the send button.", exc_info=True)

    send_button = _first_visible_locator(page, targets.send_button_selectors, timeout_ms=400)
    if send_button is not None:
        try:
            send_button.click()
            logger.info("Prompt submitted with the send button.")
            return
        except Exception:
            logger.debug("Send button click failed after Enter fallback.", exc_info=True)

    page.keyboard.press("Enter")
    logger.info("Prompt submitted with page Enter fallback.")


def _attach_files(page: Page, targets: FreeloaderPageTargets, file_paths: list[Path], logger) -> None:
    """Attach local files to the ChatGPT composer using the hidden file input."""
    resolved_paths = [str(path.resolve()) for path in file_paths if path.exists()]
    if not resolved_paths:
        return

    file_input = None
    for selector in targets.file_input_selectors:
        locator = page.locator(selector).first
        try:
            locator.wait_for(state="attached", timeout=2000)
            file_input = locator
            break
        except PlaywrightTimeoutError:
            continue

    if file_input is None:
        raise RuntimeError(
            "ChatGPT file upload control was not found. "
            "Make sure the current ChatGPT composer supports attachments."
        )

    logger.info("Uploading %s file(s) to ChatGPT.", len(resolved_paths))
    file_input.set_input_files(resolved_paths)
    page.wait_for_function(
        """
        ({ selector, expectedCount }) => {
            const input = document.querySelector(selector);
            return Boolean(input && input.files && input.files.length >= expectedCount);
        }
        """,
        arg={
            "selector": targets.file_input_selectors[0],
            "expectedCount": len(resolved_paths),
        },
        timeout=15000,
    )
    page.wait_for_timeout(600)
    logger.info("ChatGPT attachment upload has been staged in the composer.")


def _clean_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


def _extract_locator_text(locator: Locator) -> str:
    """Safely read and normalize text from a single locator."""
    try:
        return _clean_text(locator.inner_text(timeout=1000))
    except PlaywrightTimeoutError:
        return ""


def _assistant_turn_locator(page: Page, targets: FreeloaderPageTargets) -> Locator:
    """
    Return the most specific assistant-turn locator currently matching the page.

    We prefer selectors scoped under the conversation turn container so we do not
    accidentally read older markdown blocks elsewhere in the page.
    """
    fallback = page.locator(targets.assistant_turn_selectors[0])
    for selector in targets.assistant_turn_selectors:
        locator = page.locator(selector)
        if locator.count() > 0:
            return locator
    return fallback


def _generation_in_progress(page: Page, targets: FreeloaderPageTargets) -> bool:
    """Detect whether ChatGPT is still generating a reply."""
    for selector in targets.stop_button_selectors:
        locator = page.locator(selector).first
        try:
            if locator.is_visible():
                return True
        except Exception:
            continue
    return False


def _assistant_turn_count(page: Page, targets: FreeloaderPageTargets) -> int:
    """Return how many assistant turns currently exist in the conversation."""
    return _assistant_turn_locator(page, targets).count()


def _conversation_turn_count(page: Page, targets: FreeloaderPageTargets) -> int:
    """Return how many conversation turns currently exist in the thread."""
    return page.locator(targets.conversation_turn_selector).count()


def _wait_for_new_assistant_turn(
    page: Page,
    targets: FreeloaderPageTargets,
    logger,
    previous_turn_count: int,
    previous_assistant_count: int,
    timeout_seconds: int,
) -> Locator:
    """
    Ignore all existing messages and wait for a brand-new assistant turn.

    After submit, we do not read any previous assistant text again. We wait for
    fresh DOM activity, then wait for the assistant-turn count itself to increase,
    and only then bind to the newly appended assistant turn by index.
    """
    logger.info("Ignoring all existing assistant messages and waiting for a new one.")

    page.wait_for_function(
        """
        ({ turnSelector, assistantSelectors, previousTurnCount, previousAssistantCount }) => {
            const turnCount = document.querySelectorAll(turnSelector).length;
            let assistantCount = 0;

            for (const selector of assistantSelectors) {
                const count = document.querySelectorAll(selector).length;
                if (count > 0) {
                    assistantCount = count;
                    break;
                }
            }

            return (
                turnCount > previousTurnCount ||
                assistantCount > previousAssistantCount
            );
        }
        """,
        arg={
            "turnSelector": targets.conversation_turn_selector,
            "assistantSelectors": list(targets.assistant_turn_selectors),
            "previousTurnCount": previous_turn_count,
            "previousAssistantCount": previous_assistant_count,
        },
        timeout=timeout_seconds * 1000,
    )

    page.wait_for_function(
        """
        ({ assistantSelectors, previousAssistantCount }) => {
            let assistantCount = 0;

            for (const selector of assistantSelectors) {
                const count = document.querySelectorAll(selector).length;
                if (count > 0) {
                    assistantCount = count;
                    break;
                }
            }

            return assistantCount > previousAssistantCount;
        }
        """,
        arg={
            "assistantSelectors": list(targets.assistant_turn_selectors),
            "previousAssistantCount": previous_assistant_count,
        },
        timeout=timeout_seconds * 1000,
    )

    assistant_turns = _assistant_turn_locator(page, targets)
    assistant_turn = assistant_turns.nth(previous_assistant_count)
    assistant_turn.wait_for(state="attached", timeout=5000)

    logger.info(
        "Detected a new assistant turn. Previous assistant count=%s, current count=%s.",
        previous_assistant_count,
        assistant_turns.count(),
    )
    return assistant_turn


def _iter_response_updates_for_turn(
    page: Page,
    targets: FreeloaderPageTargets,
    logger,
    assistant_turn: Locator,
    timeout_seconds: int,
    poll_interval: float,
) -> Iterator[str]:
    """Yield text updates for one specific assistant turn until it stabilizes."""
    logger.info("Waiting for ChatGPT to finish responding.")
    deadline = time.time() + timeout_seconds
    latest_text = ""
    stable_cycles = 0

    while time.time() < deadline:
        current_text = _extract_locator_text(assistant_turn)
        generating = _generation_in_progress(page, targets)

        if current_text and current_text != latest_text:
            latest_text = current_text
            stable_cycles = 0
            yield latest_text
        elif current_text and current_text == latest_text:
            stable_cycles += 1

        if latest_text and not generating and stable_cycles >= 2:
            logger.info("Assistant response appears complete.")
            return

        time.sleep(poll_interval)

    if latest_text:
        logger.warning("Response wait timed out; returning the latest text seen.")
        return

    raise RuntimeError("Timed out while waiting for a ChatGPT response.")


def _wait_for_completed_response_text_for_turn(
    page: Page,
    targets: FreeloaderPageTargets,
    logger,
    assistant_turn: Locator,
    timeout_seconds: int,
    poll_interval: float,
) -> str:
    """Wait for one specific new assistant turn to finish streaming and return its final text."""
    logger.info("Waiting for the new assistant turn to finish streaming.")
    deadline = time.time() + timeout_seconds
    latest_text = ""
    stable_cycles = 0
    saw_any_text = False

    while time.time() < deadline:
        current_text = _extract_locator_text(assistant_turn)
        generating = _generation_in_progress(page, targets)

        if current_text:
            saw_any_text = True
            if current_text != latest_text:
                latest_text = current_text
                stable_cycles = 0
            else:
                stable_cycles += 1

        if saw_any_text and not generating and stable_cycles >= 2:
            logger.info("New assistant turn is complete and stable.")
            return latest_text

        time.sleep(poll_interval)

    if latest_text:
        logger.warning("Response wait timed out; returning the latest stable text seen.")
        return latest_text

    raise RuntimeError("Timed out while waiting for the new assistant response.")


def _run_stream_prompt_task(
    prompt: str,
    config,
    logger,
    attachments: list[Path],
    event_queue: queue.Queue,
) -> None:
    targets = build_page_targets(config)
    try:
        session = _ensure_worker_session(config, targets, logger)
        page = session.page
        page.bring_to_front()

        input_locator = _wait_for_chat_input(page, targets, logger)
        previous_turn_count = _conversation_turn_count(page, targets)
        previous_assistant_count = _assistant_turn_count(page, targets)

        _clear_prompt_box(page, input_locator)
        _attach_files(page, targets, attachments, logger)
        _type_prompt(page, input_locator, prompt, logger, config.type_delay_ms)
        _submit_prompt(page, input_locator, targets, logger)
        event_queue.put({"type": "submitted"})

        assistant_turn = _wait_for_new_assistant_turn(
            page,
            targets,
            logger,
            previous_turn_count=previous_turn_count,
            previous_assistant_count=previous_assistant_count,
            timeout_seconds=config.response_timeout_seconds,
        )

        for current_text in _iter_response_updates_for_turn(
            page,
            targets,
            logger,
            assistant_turn,
            timeout_seconds=config.response_timeout_seconds,
            poll_interval=config.response_poll_interval,
        ):
            event_queue.put({"type": "delta", "content": current_text})

        event_queue.put({"type": "done"})
    except Exception as exc:
        logger.exception("Freeloader browser streaming task failed.")
        _reset_worker_session(logger)
        event_queue.put({"type": "error", "error": str(exc)})


def _run_wait_prompt_task(
    prompt: str,
    config,
    logger,
    attachments: list[Path],
    event_queue: queue.Queue,
) -> None:
    targets = build_page_targets(config)
    try:
        session = _ensure_worker_session(config, targets, logger)
        page = session.page
        page.bring_to_front()

        input_locator = _wait_for_chat_input(page, targets, logger)
        previous_turn_count = _conversation_turn_count(page, targets)
        previous_assistant_count = _assistant_turn_count(page, targets)

        _clear_prompt_box(page, input_locator)
        _attach_files(page, targets, attachments, logger)
        _type_prompt(page, input_locator, prompt, logger, config.type_delay_ms)
        _submit_prompt(page, input_locator, targets, logger)
        event_queue.put({"type": "submitted"})

        assistant_turn = _wait_for_new_assistant_turn(
            page,
            targets,
            logger,
            previous_turn_count=previous_turn_count,
            previous_assistant_count=previous_assistant_count,
            timeout_seconds=config.response_timeout_seconds,
        )

        final_text = _wait_for_completed_response_text_for_turn(
            page,
            targets,
            logger,
            assistant_turn,
            timeout_seconds=config.response_timeout_seconds,
            poll_interval=config.response_poll_interval,
        )
        event_queue.put({"type": "final", "content": final_text})
    except Exception as exc:
        logger.exception("Freeloader browser final-response task failed.")
        _reset_worker_session(logger)
        event_queue.put({"type": "error", "error": str(exc)})


def warm_browser(config, logger) -> dict[str, str | bool]:
    """Warm the dedicated browser worker so later prompt sends start faster."""

    def _warmup_task():
        targets = build_page_targets(config)
        session = _ensure_worker_session(config, targets, logger)
        session.page.bring_to_front()
        _wait_for_chat_input(session.page, targets, logger)
        return {
            "warmed": True,
            "provider": "chatgpt",
            "url": session.page.url,
        }

    return _BROWSER_EXECUTOR.submit(_warmup_task).result()


def warm_chatgpt_browser(config, logger) -> dict[str, str | bool]:
    """Backward-compatible alias for older imports."""
    return warm_browser(config, logger)


def stream_prompt_response(
    prompt: str,
    config,
    logger,
    attachments: list[Path] | None = None,
    on_update: Callable[[str], None] | None = None,
    on_submitted: Callable[[], None] | None = None,
) -> Iterator[str]:
    """
    Send a prompt to ChatGPT and yield the assistant text whenever it changes.

    The browser automation runs on one dedicated worker thread so Playwright
    sync objects never cross thread boundaries.
    """
    logger.info("Starting Freeloader browser workflow.")
    event_queue: queue.Queue = queue.Queue()
    _BROWSER_EXECUTOR.submit(
        _run_stream_prompt_task,
        prompt,
        config,
        logger,
        list(attachments or []),
        event_queue,
    )

    while True:
        event = event_queue.get()
        event_type = event.get("type")

        if event_type == "submitted":
            if on_submitted is not None:
                on_submitted()
            continue

        if event_type == "delta":
            current_text = str(event.get("content") or "")
            if on_update is not None:
                on_update(current_text)
            yield current_text
            continue

        if event_type == "done":
            return

        if event_type == "error":
            raise RuntimeError(str(event.get("error") or "Freeloader browser task failed."))


def send_prompt_and_wait(
    prompt: str,
    config,
    logger,
    attachments: list[Path] | None = None,
    on_update: Callable[[str], None] | None = None,
    on_submitted: Callable[[], None] | None = None,
) -> str:
    """
    Send a prompt and return only the final completed assistant response text.

    Unlike the streaming helper, this path never surfaces partial text.
    """
    logger.info("Starting Freeloader browser workflow.")
    event_queue: queue.Queue = queue.Queue()
    _BROWSER_EXECUTOR.submit(
        _run_wait_prompt_task,
        prompt,
        config,
        logger,
        list(attachments or []),
        event_queue,
    )

    while True:
        event = event_queue.get()
        event_type = event.get("type")

        if event_type == "submitted":
            if on_submitted is not None:
                on_submitted()
            continue

        if event_type == "final":
            final_text = str(event.get("content") or "")
            if on_update is not None:
                on_update(final_text)
            return final_text

        if event_type == "error":
            raise RuntimeError(str(event.get("error") or "Freeloader browser task failed."))


def _print_response(response_text: str) -> None:
    """Print the assistant response cleanly back to the terminal."""
    separator = "=" * 24
    print(f"\n{separator}")
    print("Freeloader ChatGPT Response")
    print(f"{separator}\n")
    print(response_text)
    print()


def _show_thinking_message() -> None:
    """Show a terminal status line while ChatGPT is generating."""
    print("Freeloader is waiting for ChatGPT...", end="", flush=True)


def _clear_terminal_status_line() -> None:
    """Clear the temporary thinking line before printing the final answer."""
    print("\r" + (" " * 80) + "\r", end="", flush=True)


def _copy_to_clipboard(response_text: str, logger) -> bool:
    """Copy the final response to the Windows clipboard for easy pasting."""
    try:
        subprocess.run("clip", input=response_text, text=True, check=True, shell=True)
        logger.info("Copied the assistant response to the clipboard.")
        return True
    except Exception:
        logger.warning("Failed to copy the assistant response to the clipboard.", exc_info=True)
        return False


def run_workflow(prompt: str, config, logger) -> None:
    """CLI-friendly wrapper around the reusable browser workflow."""
    try:
        response_text = send_prompt_and_wait(
            prompt,
            config,
            logger,
            on_submitted=_show_thinking_message,
        )
    except KeyboardInterrupt:
        _clear_terminal_status_line()
        logger.warning("Interrupted by user.")
        print("\nInterrupted by user.", file=sys.stderr)
        raise
    except Exception:
        _clear_terminal_status_line()
        logger.exception("Workflow failed.")
        raise

    _clear_terminal_status_line()
    _print_response(response_text)
    if _copy_to_clipboard(response_text, logger):
        print("Copied to clipboard. Paste it anywhere with Ctrl+V.\n")
