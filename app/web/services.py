from __future__ import annotations

from dataclasses import dataclass
from logging import Logger

from app.config import AppConfig
from app.storage import ChatStore


@dataclass(slots=True)
class WebServices:
    """Shared application services used by the Flask web routes."""

    config: AppConfig
    logger: Logger
    store: ChatStore
