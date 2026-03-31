from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright


DEFAULT_CDP_ENDPOINT = "http://127.0.0.1:9222"


@dataclass(slots=True)
class FreeloaderBrowserSession:
    """Connected Playwright session for an already running Brave instance."""

    playwright: Playwright
    browser: Browser
    context: BrowserContext
    page: Page


def _cdp_endpoint_is_ready(cdp_endpoint: str, timeout_seconds: float = 2.0) -> bool:
    """Return True when Brave is already exposing the requested CDP endpoint."""
    version_url = f"{cdp_endpoint.rstrip('/')}/json/version"
    try:
        with urlopen(version_url, timeout=timeout_seconds) as response:
            return response.status == 200
    except URLError:
        return False


def get_browser_status(config) -> dict[str, str | bool]:
    """Return a small status payload for the local UI and API responses."""
    brave_path = Path(config.brave_path)
    cdp_endpoint = getattr(config, "cdp_endpoint", DEFAULT_CDP_ENDPOINT)
    path_exists = brave_path.exists()
    endpoint_ready = _cdp_endpoint_is_ready(cdp_endpoint) if path_exists else False

    if path_exists and endpoint_ready:
        message = "Attached to Brave"
    elif not path_exists:
        message = f"Brave not found at {brave_path}"
    else:
        message = "Brave is not exposing remote debugging on port 9222"

    return {
        "connected": path_exists and endpoint_ready,
        "message": message,
        "cdp_endpoint": cdp_endpoint,
        "brave_path": str(brave_path),
    }


def _find_or_create_chat_page(context: BrowserContext, chat_url: str, logger) -> Page:
    """Reuse an existing ChatGPT tab when possible, otherwise open a new one."""
    for page in context.pages:
        current_url = page.url or ""
        if current_url.startswith(chat_url) or "chatgpt.com" in current_url:
            logger.info("Reusing existing ChatGPT tab: %s", current_url)
            return page

    logger.info("Opening a new tab for ChatGPT.")
    page = context.new_page()
    page.goto(chat_url, wait_until="domcontentloaded", timeout=60000)
    return page


def launch_browser_session(config, logger) -> FreeloaderBrowserSession:
    """
    Connect Playwright to an already running Brave instance over CDP.

    This uses the user's Brave session on port 9222 and does not launch a fresh
    Playwright-managed browser. If Brave is not running with remote debugging
    enabled, a friendly error is raised with a launch example.
    """
    brave_path = Path(config.brave_path)
    cdp_endpoint = getattr(config, "cdp_endpoint", DEFAULT_CDP_ENDPOINT)

    if not brave_path.exists():
        raise FileNotFoundError(
            f"Brave executable not found at: {brave_path}. "
            "Update BRAVE_PATH in your .env file."
        )

    if not _cdp_endpoint_is_ready(cdp_endpoint):
        raise RuntimeError(
            "Brave is not exposing a remote debugging endpoint on port 9222.\n"
            "Close all Brave windows, then start Brave manually with:\n"
            f'"{brave_path}" --remote-debugging-port=9222\n'
            "After Brave is running, sign in to ChatGPT if needed and run this tool again."
        )

    logger.info("Connecting to existing Brave via CDP: %s", cdp_endpoint)
    playwright = sync_playwright().start()

    try:
        browser = playwright.chromium.connect_over_cdp(cdp_endpoint, timeout=15000)
        if not browser.contexts:
            raise RuntimeError(
                "Connected to Brave, but no default browser context was exposed over CDP. "
                "Restart Brave with remote debugging enabled and try again."
            )

        context = browser.contexts[0]
        logger.info("Attached to the default Brave context.")
        context.set_default_timeout(15000)
        page = _find_or_create_chat_page(context, config.chatgpt_url, logger)

        if not page.url.startswith(config.chatgpt_url):
            logger.info("Navigating to ChatGPT: %s", config.chatgpt_url)
            page.goto(config.chatgpt_url, wait_until="domcontentloaded", timeout=60000)

        logger.info("Connected to Brave and ready at: %s", page.url)
        return FreeloaderBrowserSession(
            playwright=playwright,
            browser=browser,
            context=context,
            page=page,
        )
    except Exception:
        logger.exception("Failed to connect to Brave over CDP.")
        playwright.stop()
        raise


def close_browser_session(session: FreeloaderBrowserSession, logger) -> None:
    """
    Disconnect Playwright from the existing Brave instance.

    We intentionally do not close the user's Brave browser or its context.
    """
    logger.info("Stopping Playwright and detaching from Brave.")
    try:
        session.playwright.stop()
    except Exception:
        pass
