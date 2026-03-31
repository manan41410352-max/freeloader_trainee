from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


# Resolve project paths from the package location so the app works from the VS Code terminal.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"


def _resolve_path(raw_value: str | None, fallback: Path) -> Path:
    """Return an absolute path from .env, or a sensible project-local fallback."""
    if raw_value:
        candidate = Path(raw_value).expanduser()
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
        return candidate.resolve()
    return fallback.resolve()


def _parse_bool(raw_value: str | None, default: bool = False) -> bool:
    """Parse simple true/false text values from environment variables."""
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def guess_brave_path() -> Path:
    """Best-effort default for common Brave install locations on Windows."""
    candidates = [
        Path("C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe"),
        Path("C:/Program Files (x86)/BraveSoftware/Brave-Browser/Application/brave.exe"),
        Path.home() / "AppData/Local/BraveSoftware/Brave-Browser/Application/brave.exe",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


@dataclass(slots=True)
class AppConfig:
    """Shared settings object for the Freeloader web and CLI entrypoints."""

    project_root: Path
    data_dir: Path
    database_path: Path
    logs_dir: Path
    log_file: Path
    log_level: str
    chatgpt_url: str
    brave_path: Path
    user_data_dir: Path
    cdp_endpoint: str
    headless: bool
    type_delay_ms: int
    response_timeout_seconds: int
    response_poll_interval: float
    chat_input_selector: str
    response_selector: str
    ollama_base_url: str
    default_ollama_model: str
    ollama_keep_alive: str
    ollama_history_message_limit: int
    ollama_history_char_limit: int
    chatgpt_launch_delay_ms: int
    whisper_model_path: Path
    web_host: str
    web_port: int


def load_config() -> AppConfig:
    """Load local settings from .env and provide project defaults."""
    load_dotenv(ENV_FILE)

    data_dir = _resolve_path(os.getenv("DATA_DIR"), PROJECT_ROOT / "data")
    logs_dir = _resolve_path(os.getenv("LOGS_DIR"), PROJECT_ROOT / "logs")

    return AppConfig(
        project_root=PROJECT_ROOT,
        data_dir=data_dir,
        database_path=_resolve_path(os.getenv("DATABASE_PATH"), data_dir / "chats.json"),
        logs_dir=logs_dir,
        log_file=_resolve_path(os.getenv("LOG_FILE"), logs_dir / "app.log"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        chatgpt_url=os.getenv("CHATGPT_URL", "https://chatgpt.com/"),
        brave_path=_resolve_path(os.getenv("BRAVE_PATH"), guess_brave_path()),
        user_data_dir=_resolve_path(
            os.getenv("USER_DATA_DIR"),
            PROJECT_ROOT / "playwright_state" / "brave_profile",
        ),
        cdp_endpoint=os.getenv("CDP_ENDPOINT", "http://127.0.0.1:9222"),
        headless=_parse_bool(os.getenv("HEADLESS"), default=False),
        type_delay_ms=int(os.getenv("TYPE_DELAY_MS", "35")),
        response_timeout_seconds=int(os.getenv("RESPONSE_TIMEOUT_SECONDS", "180")),
        response_poll_interval=float(os.getenv("RESPONSE_POLL_INTERVAL", "1.0")),
        chat_input_selector=os.getenv("CHAT_INPUT_SELECTOR", "textarea"),
        response_selector=os.getenv(
            "RESPONSE_SELECTOR",
            "[data-message-author-role='assistant']",
        ),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        default_ollama_model=os.getenv("DEFAULT_OLLAMA_MODEL", "llama3.1:8b"),
        ollama_keep_alive=os.getenv("OLLAMA_KEEP_ALIVE", "30m"),
        ollama_history_message_limit=max(2, int(os.getenv("OLLAMA_HISTORY_MESSAGE_LIMIT", "10"))),
        ollama_history_char_limit=max(2000, int(os.getenv("OLLAMA_HISTORY_CHAR_LIMIT", "18000"))),
        chatgpt_launch_delay_ms=max(0, int(os.getenv("CHATGPT_LAUNCH_DELAY_MS", "0"))),
        whisper_model_path=_resolve_path(
            os.getenv("WHISPER_MODEL_PATH"),
            Path.home() / ".ollama" / "models" / "external" / "Oriserve-Whisper-Hindi2Hinglish-Apex",
        ),
        web_host=os.getenv("WEB_HOST", "127.0.0.1"),
        web_port=int(os.getenv("WEB_PORT", "5000")),
    )
