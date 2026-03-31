from __future__ import annotations

import queue
import tempfile
import time
import uuid
from pathlib import Path
from threading import Thread

from flask import Flask, Response, jsonify, request, stream_with_context
from werkzeug.utils import secure_filename

from app.attachments import build_ollama_user_content, enrich_attachments_for_ollama
from app.freeloader.workflow import stream_prompt_response
from app.ollama_client import resolve_ollama_model, stream_ollama_response
from app.web.helpers import build_shell_payload, default_attachment_prompt, json_line
from app.web.services import WebServices


def _cleanup_temp_paths(temp_paths: list[Path]) -> None:
    for temp_path in temp_paths:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def _stage_uploaded_attachments(uploaded_files, logger) -> tuple[list[Path], list[dict]]:
    temp_attachment_paths: list[Path] = []
    attachment_metadata: list[dict] = []

    for uploaded_file in uploaded_files:
        safe_name = secure_filename(uploaded_file.filename or "") or "attachment"
        suffix = Path(safe_name).suffix or ".bin"
        with tempfile.NamedTemporaryFile(
            prefix="freeloader_attachment_",
            suffix=suffix,
            delete=False,
        ) as temp_file:
            uploaded_file.save(temp_file)
            temp_path = Path(temp_file.name)

        temp_attachment_paths.append(temp_path)
        attachment_metadata.append(
            {
                "name": safe_name,
                "size_bytes": temp_path.stat().st_size,
                "content_type": uploaded_file.mimetype or "",
            }
        )

    logger.info("Staged %s uploaded attachment(s) for processing.", len(temp_attachment_paths))
    return temp_attachment_paths, attachment_metadata


def _resolve_provider_runtime(
    requested_model: str,
    services: WebServices,
) -> tuple[dict, list[str], dict[str, str], str | None]:
    shell_payload = build_shell_payload(services)
    statuses = shell_payload.get("status") or {}

    active_providers: list[str] = []
    unavailable_providers: dict[str, str] = {}

    chatgpt_status = statuses.get("chatgpt") or {}
    if chatgpt_status.get("connected"):
        active_providers.append("chatgpt")
    else:
        unavailable_providers["chatgpt"] = str(
            chatgpt_status.get("message") or "ChatGPT is unavailable."
        )

    ollama_model: str | None = None
    ollama_status = statuses.get("ollama") or {}
    if ollama_status.get("connected"):
        try:
            ollama_model = resolve_ollama_model(requested_model, services.config, logger=services.logger)
            active_providers.append("ollama")
        except Exception as exc:
            unavailable_providers["ollama"] = str(exc)
    else:
        unavailable_providers["ollama"] = str(
            ollama_status.get("message") or "Ollama is unavailable."
        )

    return shell_payload, active_providers, unavailable_providers, ollama_model


def _build_no_provider_error(unavailable_providers: dict[str, str]) -> str:
    chatgpt_error = unavailable_providers.get("chatgpt") or "ChatGPT is unavailable."
    ollama_error = unavailable_providers.get("ollama") or "Ollama is unavailable."
    return f"Neither ChatGPT nor Ollama is ready. {chatgpt_error}. {ollama_error}."


def register_message_routes(flask_app: Flask, services: WebServices) -> None:
    """Register the streaming send route used by the dual-chat UI."""

    @flask_app.post("/api/send")
    def send_message():
        uploaded_files = []
        if request.files or request.form:
            payload = request.form
            uploaded_files = [
                uploaded_file
                for uploaded_file in request.files.getlist("attachments")
                if uploaded_file is not None and uploaded_file.filename
            ]
        else:
            payload = request.get_json(silent=True) or {}

        chat_id = (payload.get("chat_id") or "").strip()
        message = (payload.get("message") or "").strip()
        requested_model = (payload.get("ollama_model") or "").strip()
        temp_attachment_paths: list[Path] = []
        attachment_metadata: list[dict] = []

        try:
            temp_attachment_paths, attachment_metadata = _stage_uploaded_attachments(
                uploaded_files,
                services.logger,
            )
        except Exception as exc:
            _cleanup_temp_paths(temp_attachment_paths)
            services.logger.exception("Unable to stage uploaded attachments.")
            return jsonify({"error": str(exc)}), 400

        if not message and not attachment_metadata:
            _cleanup_temp_paths(temp_attachment_paths)
            return jsonify({"error": "Message cannot be empty."}), 400

        effective_message = message or default_attachment_prompt(len(attachment_metadata))
        attachment_metadata = enrich_attachments_for_ollama(
            temp_attachment_paths,
            attachment_metadata,
            services.logger,
        )
        ollama_prompt = build_ollama_user_content(effective_message, attachment_metadata)

        shell_payload, active_providers, unavailable_providers, ollama_model = _resolve_provider_runtime(
            requested_model,
            services,
        )

        if not active_providers:
            _cleanup_temp_paths(temp_attachment_paths)
            return jsonify(
                {
                    "error": _build_no_provider_error(unavailable_providers),
                    **shell_payload,
                }
            ), 503

        chat = services.store.get_chat(chat_id) if chat_id else None
        chat_created = False
        if chat is None:
            chat = services.store.create_chat(title="New Chat")
            chat_id = chat["id"]
            chat_created = True

        ollama_history: list[dict] = []
        if ollama_model:
            ollama_history = services.store.build_ollama_history(
                chat_id,
                ollama_model,
                max_messages=services.config.ollama_history_message_limit,
                max_chars=services.config.ollama_history_char_limit,
            )
        turn_id = uuid.uuid4().hex
        user_message = services.store.add_message(
            chat_id,
            "user",
            effective_message,
            provider="user",
            turn_id=turn_id,
            attachments=attachment_metadata,
        )

        event_queue: queue.Queue[dict] = queue.Queue()
        providers = set(active_providers)

        def emit(event_type: str, **event_payload) -> None:
            event_queue.put({"type": event_type, **event_payload})

        def run_chatgpt_worker() -> None:
            latest_text = ""
            try:
                emit("provider_status", provider="chatgpt", turn_id=turn_id, state="thinking")
                for current_text in stream_prompt_response(
                    effective_message,
                    services.config,
                    services.logger,
                    attachments=temp_attachment_paths,
                ):
                    latest_text = current_text
                    emit(
                        "provider_delta",
                        provider="chatgpt",
                        turn_id=turn_id,
                        content=current_text,
                    )

                if not latest_text.strip():
                    raise RuntimeError("ChatGPT returned an empty response.")

                assistant_message = services.store.add_message(
                    chat_id,
                    "assistant",
                    latest_text,
                    provider="chatgpt",
                    model_name="ChatGPT",
                    turn_id=turn_id,
                )
                emit(
                    "provider_final",
                    provider="chatgpt",
                    turn_id=turn_id,
                    message=assistant_message,
                )
            except Exception as exc:
                services.logger.exception("ChatGPT worker failed for chat_id=%s", chat_id)
                emit(
                    "provider_error",
                    provider="chatgpt",
                    turn_id=turn_id,
                    error=str(exc),
                )
            finally:
                emit("provider_done", provider="chatgpt", turn_id=turn_id)

        def run_chatgpt_worker_with_head_start() -> None:
            launch_delay_seconds = max(0, services.config.chatgpt_launch_delay_ms) / 1000
            if launch_delay_seconds > 0:
                time.sleep(launch_delay_seconds)
            run_chatgpt_worker()

        def run_ollama_worker() -> None:
            latest_text = ""
            try:
                emit(
                    "provider_status",
                    provider="ollama",
                    model_name=ollama_model,
                    turn_id=turn_id,
                    state="thinking",
                )
                for current_text in stream_ollama_response(
                    ollama_prompt,
                    ollama_model,
                    ollama_history,
                    services.config,
                    services.logger,
                ):
                    latest_text = current_text
                    emit(
                        "provider_delta",
                        provider="ollama",
                        model_name=ollama_model,
                        turn_id=turn_id,
                        content=current_text,
                    )

                if not latest_text.strip():
                    raise RuntimeError("Ollama returned an empty response.")

                assistant_message = services.store.add_message(
                    chat_id,
                    "assistant",
                    latest_text,
                    provider="ollama",
                    model_name=ollama_model,
                    turn_id=turn_id,
                )
                emit(
                    "provider_final",
                    provider="ollama",
                    model_name=ollama_model,
                    turn_id=turn_id,
                    message=assistant_message,
                )
            except Exception as exc:
                services.logger.exception(
                    "Ollama worker failed for chat_id=%s using model=%s",
                    chat_id,
                    ollama_model,
                )
                emit(
                    "provider_error",
                    provider="ollama",
                    model_name=ollama_model,
                    turn_id=turn_id,
                    error=str(exc),
                )
            finally:
                emit(
                    "provider_done",
                    provider="ollama",
                    model_name=ollama_model,
                    turn_id=turn_id,
                )

        @stream_with_context
        def generate():
            try:
                yield json_line(
                    {
                        "type": "start",
                        "chat_id": chat_id,
                        "chat_created": chat_created,
                        "turn_id": turn_id,
                        "user_message": user_message,
                        "active_providers": active_providers,
                        "unavailable_providers": unavailable_providers,
                        "ollama_model": ollama_model,
                        **shell_payload,
                    }
                )

                for provider_name, error_text in unavailable_providers.items():
                    yield json_line(
                        {
                            "type": "provider_error",
                            "provider": provider_name,
                            "turn_id": turn_id,
                            "error": error_text,
                        }
                    )
                    yield json_line(
                        {
                            "type": "provider_done",
                            "provider": provider_name,
                            "turn_id": turn_id,
                        }
                    )

                if "ollama" in providers:
                    Thread(target=run_ollama_worker, daemon=True).start()
                if "chatgpt" in providers:
                    Thread(target=run_chatgpt_worker_with_head_start, daemon=True).start()

                completed: set[str] = set()
                while completed != providers:
                    try:
                        event = event_queue.get(timeout=1.0)
                    except queue.Empty:
                        continue

                    if event["type"] == "provider_done":
                        completed.add(str(event["provider"]))

                    yield json_line(event)

                yield json_line(
                    {
                        "type": "complete",
                        "chat": services.store.get_chat(chat_id),
                        "chat_id": chat_id,
                        "ollama_model": ollama_model,
                        **build_shell_payload(services),
                    }
                )
            finally:
                _cleanup_temp_paths(temp_attachment_paths)

        return Response(generate(), mimetype="application/x-ndjson")
