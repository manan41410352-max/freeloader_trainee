from __future__ import annotations

import logging

from app.config import AppConfig


def setup_logging(config: AppConfig) -> logging.Logger:
    """Configure console + file logging for easy debugging from VS Code."""
    config.logs_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("freeloader")
    logger.setLevel(getattr(logging, config.log_level.upper(), logging.INFO))
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(config.log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger
