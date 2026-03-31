from __future__ import annotations

import json

from app.freeloader.browser import get_browser_status
from app.ollama_client import list_ollama_models
from app.web.services import WebServices


def json_line(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"


def default_attachment_prompt(attachment_count: int) -> str:
    return (
        "Please analyze the attached file."
        if attachment_count == 1
        else "Please analyze the attached files."
    )


def build_shell_payload(services: WebServices) -> dict:
    config = services.config
    logger = services.logger
    ollama_models = list_ollama_models(config, logger=logger)
    selected_model = config.default_ollama_model.strip()
    if not selected_model and ollama_models:
        selected_model = ollama_models[0]["name"]

    return {
        "status": {
            "chatgpt": get_browser_status(config),
            "ollama": {
                "connected": bool(ollama_models),
                "message": (
                    f"Ollama ready ({len(ollama_models)} model{'s' if len(ollama_models) != 1 else ''})"
                    if ollama_models
                    else f"Ollama not reachable at {config.ollama_base_url}"
                ),
                "base_url": config.ollama_base_url,
                "model_count": len(ollama_models),
            },
        },
        "ollama_models": ollama_models,
        "default_ollama_model": selected_model,
    }
