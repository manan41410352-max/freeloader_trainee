from __future__ import annotations

from dataclasses import dataclass

from app.config import AppConfig


DEFAULT_CHAT_INPUT_SELECTORS = (
    "#prompt-textarea",
    "textarea[placeholder*='Message']",
    "textarea[placeholder*='Ask anything']",
    "textarea",
    "[contenteditable='true'][role='textbox']",
    "div.ProseMirror[contenteditable='true']",
)

DEFAULT_SEND_BUTTON_SELECTORS = (
    "button[data-testid='send-button']",
    "button[aria-label*='Send']",
    "button:has-text('Send')",
)

DEFAULT_FILE_INPUT_SELECTORS = (
    "input#upload-files",
    "input[type='file']#upload-files",
    "input[type='file']:not([accept='image/*'])",
    "input[type='file']",
)

DEFAULT_STOP_BUTTON_SELECTORS = (
    "button[data-testid='stop-button']",
    "button[aria-label*='Stop']",
    "button:has-text('Stop generating')",
    "button:has-text('Stop')",
)

DEFAULT_ASSISTANT_MESSAGE_SELECTORS = (
    "[data-testid='conversation-turn'] [data-message-author-role='assistant']",
    "[data-testid*='conversation-turn'] [data-message-author-role='assistant']",
    "[data-message-author-role='assistant']",
    "article [data-message-author-role='assistant']",
    "main article",
    "main [class*='markdown']",
)

DEFAULT_ASSISTANT_TURN_SELECTORS = (
    "[data-testid='conversation-turn'] [data-message-author-role='assistant']",
    "[data-testid*='conversation-turn'] [data-message-author-role='assistant']",
    "[data-message-author-role='assistant']",
)

DEFAULT_CONVERSATION_TURN_SELECTOR = "[data-testid='conversation-turn'], [data-testid*='conversation-turn']"


def _merge_unique_selectors(primary: str | None, fallbacks: tuple[str, ...]) -> tuple[str, ...]:
    ordered = [selector.strip() for selector in [primary or "", *fallbacks] if selector and selector.strip()]
    seen: set[str] = set()
    unique: list[str] = []
    for selector in ordered:
        if selector in seen:
            continue
        seen.add(selector)
        unique.append(selector)
    return tuple(unique)


@dataclass(slots=True, frozen=True)
class FreeloaderPageTargets:
    """Selectors and URLs used by Freeloader while driving the ChatGPT page."""

    chat_url: str
    chat_input_selectors: tuple[str, ...]
    send_button_selectors: tuple[str, ...]
    file_input_selectors: tuple[str, ...]
    stop_button_selectors: tuple[str, ...]
    assistant_message_selectors: tuple[str, ...]
    assistant_turn_selectors: tuple[str, ...]
    conversation_turn_selector: str


def build_page_targets(config: AppConfig) -> FreeloaderPageTargets:
    """Build the active selector set from config plus stable fallbacks."""
    assistant_selectors = _merge_unique_selectors(config.response_selector, DEFAULT_ASSISTANT_MESSAGE_SELECTORS)
    assistant_turn_selectors = _merge_unique_selectors(config.response_selector, DEFAULT_ASSISTANT_TURN_SELECTORS)

    return FreeloaderPageTargets(
        chat_url=config.chatgpt_url,
        chat_input_selectors=_merge_unique_selectors(config.chat_input_selector, DEFAULT_CHAT_INPUT_SELECTORS),
        send_button_selectors=DEFAULT_SEND_BUTTON_SELECTORS,
        file_input_selectors=DEFAULT_FILE_INPUT_SELECTORS,
        stop_button_selectors=DEFAULT_STOP_BUTTON_SELECTORS,
        assistant_message_selectors=assistant_selectors,
        assistant_turn_selectors=assistant_turn_selectors,
        conversation_turn_selector=DEFAULT_CONVERSATION_TURN_SELECTOR,
    )
