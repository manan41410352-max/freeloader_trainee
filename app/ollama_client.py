from __future__ import annotations

import json
import time
from typing import Iterator

import requests


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


def _ollama_error_text(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        for key in ("error", "message"):
            value = payload.get(key)
            if value:
                return str(value).strip()
        return json.dumps(payload, ensure_ascii=False)

    return (response.text or "").strip()


def _is_retryable_ollama_exception(exc: Exception) -> bool:
    if isinstance(exc, requests.RequestException):
        return True
    message = str(exc).lower()
    return "500" in message or "internal server error" in message


def warm_ollama_model(model_name: str, config, logger=None) -> dict:
    """Load a model into memory so the next chat request starts faster."""
    url = _join_url(config.ollama_base_url, "/api/chat")
    payload = {
        "model": model_name,
        "messages": [],
        "stream": False,
        "keep_alive": config.ollama_keep_alive,
    }

    response = requests.post(url, json=payload, timeout=(5, 120))
    if response.status_code >= 400:
        error_text = _ollama_error_text(response)
        raise RuntimeError(
            error_text
            or f"Unable to warm Ollama model '{model_name}' (HTTP {response.status_code})."
        )

    result = response.json()
    if logger is not None:
        logger.info(
            "Warmed Ollama model '%s' with keep_alive=%s.",
            model_name,
            config.ollama_keep_alive,
        )
    return result


def list_ollama_models(config, logger=None) -> list[dict]:
    """Return installed Ollama models from the local Ollama HTTP API."""
    url = _join_url(config.ollama_base_url, "/api/tags")
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        if logger is not None:
            logger.warning("Unable to fetch Ollama models from %s.", url, exc_info=True)
        return []

    models: list[dict] = []
    for item in payload.get("models", []):
        name = (item.get("name") or "").strip()
        if not name:
            continue
        models.append(
            {
                "name": name,
                "size": item.get("size"),
                "modified_at": item.get("modified_at"),
            }
        )

    return models


def get_ollama_status(config, logger=None) -> dict[str, str | bool | int]:
    """Return a small status payload for the local Ollama service."""
    models = list_ollama_models(config, logger=logger)
    connected = bool(models)

    if connected:
        message = f"Ollama ready ({len(models)} model{'s' if len(models) != 1 else ''})"
    else:
        message = f"Ollama not reachable at {config.ollama_base_url}"

    return {
        "connected": connected,
        "message": message,
        "base_url": config.ollama_base_url,
        "model_count": len(models),
    }


def resolve_ollama_model(requested_model: str | None, config, logger=None) -> str:
    """Pick the requested model, the configured default, or the first installed model."""
    preferred = (requested_model or "").strip() or config.default_ollama_model.strip()
    models = list_ollama_models(config, logger=logger)
    available_names = {model["name"] for model in models}

    if preferred and preferred in available_names:
        return preferred
    if preferred and preferred not in available_names:
        raise RuntimeError(
            f"Ollama model '{preferred}' is not installed. "
            f"Available models: {', '.join(sorted(available_names)) or 'none'}."
        )
    if models:
        return models[0]["name"]

    raise RuntimeError(
        "No Ollama models were found. Start Ollama and pull a model first, "
        "for example: ollama pull llama3.2"
    )


def stream_ollama_response(
    prompt: str,
    model_name: str,
    history: list[dict],
    config,
    logger,
) -> Iterator[str]:
    """
    Stream a response from Ollama and yield the cumulative assistant text.

    We use `/api/chat` so the selected local model can see the local conversation
    history for this chat.
    """
    url = _join_url(config.ollama_base_url, "/api/chat")
    payload = {
        "model": model_name,
        "messages": [*history, {"role": "user", "content": prompt}],
        "stream": True,
        "keep_alive": config.ollama_keep_alive,
    }

    logger.info("Sending prompt to Ollama model '%s'.", model_name)
    max_attempts = 2

    for attempt in range(1, max_attempts + 1):
        accumulated = ""
        yielded_any_tokens = False

        try:
            with requests.post(
                url,
                json=payload,
                stream=True,
                timeout=(5, config.response_timeout_seconds),
            ) as response:
                if response.status_code >= 400:
                    error_text = _ollama_error_text(response)
                    raise RuntimeError(
                        error_text
                        or f"Ollama request failed with HTTP {response.status_code} for model '{model_name}'."
                    )

                for raw_line in response.iter_lines(decode_unicode=True):
                    if not raw_line:
                        continue

                    event = json.loads(raw_line)
                    if event.get("error"):
                        raise RuntimeError(str(event["error"]))

                    delta = (
                        event.get("message", {}).get("content")
                        or event.get("response")
                        or ""
                    )
                    if delta:
                        accumulated += delta
                        yielded_any_tokens = True
                        yield accumulated

                    if event.get("done"):
                        return

            return
        except Exception as exc:
            should_retry = (
                attempt < max_attempts
                and not yielded_any_tokens
                and _is_retryable_ollama_exception(exc)
            )
            if should_retry:
                wait_seconds = 1.0 * attempt
                logger.warning(
                    "Ollama request failed for model '%s' on attempt %s/%s: %s. Retrying in %.1fs.",
                    model_name,
                    attempt,
                    max_attempts,
                    exc,
                    wait_seconds,
                )
                time.sleep(wait_seconds)
                continue
            raise
