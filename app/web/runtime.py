from __future__ import annotations

import tempfile
from pathlib import Path

from flask import Flask, jsonify, request

from app.freeloader.workflow import warm_browser
from app.ollama_client import resolve_ollama_model, warm_ollama_model
from app.web.helpers import build_shell_payload
from app.web.services import WebServices


class SpeechUnavailableError(RuntimeError):
    """Raised when the local speech stack cannot be imported on this machine."""


def _load_speech_module():
    try:
        from app import speech
    except Exception as exc:
        raise SpeechUnavailableError(
            "Voice transcription is unavailable because the local speech dependencies "
            f"could not be imported: {exc}"
        ) from exc
    return speech


def warm_transcriber(config, logger):
    speech = _load_speech_module()
    return speech.warm_transcriber(config, logger)


def transcribe_audio_file(audio_path: Path, config, logger) -> str:
    speech = _load_speech_module()
    return speech.transcribe_audio_file(audio_path, config, logger)


def register_runtime_routes(flask_app: Flask, services: WebServices) -> None:
    """Register warmup, runtime status, and voice transcription routes."""

    @flask_app.post("/api/transcribe/warmup")
    def warm_voice_model():
        try:
            payload = warm_transcriber(services.config, services.logger)
        except SpeechUnavailableError as exc:
            services.logger.warning("Voice model warmup skipped because speech dependencies are unavailable.")
            return jsonify({"error": str(exc)}), 503
        except Exception as exc:
            services.logger.exception("Voice model warmup failed.")
            return jsonify({"error": str(exc)}), 503

        return jsonify(payload)

    @flask_app.post("/api/ollama/warmup")
    def warm_local_ollama_model():
        raw_payload = request.get_json(silent=True)
        payload = raw_payload if isinstance(raw_payload, dict) else request.form
        requested_model = (payload.get("model") or "").strip()

        try:
            model_name = resolve_ollama_model(requested_model, services.config, logger=services.logger)
            result = warm_ollama_model(model_name, services.config, logger=services.logger)
        except Exception as exc:
            services.logger.exception("Ollama model warmup failed for requested_model=%s", requested_model)
            return jsonify({"error": str(exc), **build_shell_payload(services)}), 503

        return jsonify(
            {
                "warmed": True,
                "model": model_name,
                "keep_alive": services.config.ollama_keep_alive,
                "result": result,
                **build_shell_payload(services),
            }
        )

    @flask_app.post("/api/browser/warmup")
    def warm_freeloader_browser():
        try:
            result = warm_browser(services.config, services.logger)
        except Exception as exc:
            services.logger.exception("Freeloader browser warmup failed.")
            return jsonify({"error": str(exc), **build_shell_payload(services)}), 503

        return jsonify(
            {
                **result,
                **build_shell_payload(services),
            }
        )

    @flask_app.post("/api/transcribe")
    def transcribe_audio():
        if (request.content_length or 0) > 20 * 1024 * 1024:
            return jsonify({"error": "Audio upload is too large."}), 413

        uploaded_audio = request.files.get("audio")
        if uploaded_audio is None or not uploaded_audio.filename:
            return jsonify({"error": "No audio file was uploaded."}), 400

        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix="freeloader_voice_",
                suffix=".wav",
                delete=False,
            ) as temp_file:
                uploaded_audio.save(temp_file)
                temp_path = Path(temp_file.name)

            transcript = transcribe_audio_file(temp_path, services.config, services.logger)
            return jsonify(
                {
                    "text": transcript,
                    "provider": "local-whisper",
                    "model_path": str(services.config.whisper_model_path),
                }
            )
        except FileNotFoundError as exc:
            services.logger.exception("Voice model path is unavailable.")
            return jsonify({"error": str(exc)}), 503
        except SpeechUnavailableError as exc:
            services.logger.warning("Voice transcription is unavailable on this machine.")
            return jsonify({"error": str(exc)}), 503
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            services.logger.exception("Voice transcription request failed.")
            return jsonify({"error": str(exc)}), 500
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink(missing_ok=True)
