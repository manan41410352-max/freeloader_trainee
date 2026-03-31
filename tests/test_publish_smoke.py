from __future__ import annotations

import io
import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from app.config import AppConfig
from app.server import create_app


@pytest.fixture()
def app_client(tmp_path: Path):
    data_dir = tmp_path / "data"
    logs_dir = tmp_path / "logs"
    data_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    config = AppConfig(
        project_root=Path.cwd(),
        data_dir=data_dir,
        database_path=data_dir / "chats.json",
        logs_dir=logs_dir,
        log_file=logs_dir / "app.log",
        log_level="INFO",
        chatgpt_url="https://chatgpt.com/",
        brave_path=Path("C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe"),
        user_data_dir=tmp_path / "playwright_state",
        cdp_endpoint="http://127.0.0.1:9222",
        headless=False,
        type_delay_ms=0,
        response_timeout_seconds=30,
        response_poll_interval=0.05,
        chat_input_selector="textarea",
        response_selector="[data-message-author-role='assistant']",
        ollama_base_url="http://127.0.0.1:11434",
        default_ollama_model="llama3.1:8b",
        ollama_keep_alive="30m",
        ollama_history_message_limit=10,
        ollama_history_char_limit=18000,
        chatgpt_launch_delay_ms=0,
        whisper_model_path=tmp_path / "models" / "whisper",
        web_host="127.0.0.1",
        web_port=5000,
    )

    logger = logging.getLogger(f"freeloader-test-{tmp_path.name}")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)

    with patch("app.server.load_config", return_value=config), patch("app.server.setup_logging", return_value=logger):
        app = create_app()

    with patch("app.web.helpers.list_ollama_models", return_value=[{"name": "llama3.1:8b"}]), patch(
        "app.web.helpers.get_browser_status",
        return_value={"connected": True, "message": "Attached to Brave", "cdp_endpoint": config.cdp_endpoint},
    ):
        yield app.test_client()


def test_index_and_chat_listing_render(app_client):
    index_response = app_client.get("/")
    chats_response = app_client.get("/api/chats")

    assert index_response.status_code == 200
    assert "initialShellPayload" in index_response.get_data(as_text=True)
    assert chats_response.status_code == 200
    assert "chats" in chats_response.get_json()


def test_chat_lifecycle_routes(app_client):
    create_response = app_client.post("/api/chats", json={"title": "Smoke Chat"})
    assert create_response.status_code == 201
    payload = create_response.get_json()
    chat_id = payload["chat"]["id"]

    get_response = app_client.get(f"/api/chats/{chat_id}")
    assert get_response.status_code == 200
    assert get_response.get_json()["chat"]["title"] == "Smoke Chat"

    delete_response = app_client.delete(f"/api/chats/{chat_id}")
    assert delete_response.status_code == 200
    assert delete_response.get_json()["deleted"] is True


def test_send_route_streams_both_providers(app_client):
    with patch("app.web.messages.resolve_ollama_model", return_value="llama3.1:8b"), patch(
        "app.web.messages.stream_prompt_response",
        return_value=iter(["chatgpt answer"]),
    ), patch(
        "app.web.messages.stream_ollama_response",
        return_value=iter(["ollama answer"]),
    ):
        response = app_client.post(
            "/api/send",
            json={"message": "hello world", "ollama_model": "llama3.1:8b"},
        )
        body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.mimetype == "application/x-ndjson"
    assert '"type": "start"' in body
    assert '"type": "provider_final"' in body
    assert "chatgpt answer" in body
    assert "ollama answer" in body


def test_send_route_accepts_form_payload_without_files(app_client):
    with patch("app.web.messages.resolve_ollama_model", return_value="llama3.1:8b"), patch(
        "app.web.messages.stream_prompt_response",
        return_value=iter(["chatgpt form answer"]),
    ), patch(
        "app.web.messages.stream_ollama_response",
        return_value=iter(["ollama form answer"]),
    ):
        response = app_client.post(
            "/api/send",
            data={"message": "hello form", "ollama_model": "llama3.1:8b"},
        )
        body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "chatgpt form answer" in body
    assert "ollama form answer" in body


def test_runtime_warmup_and_transcribe_routes(app_client):
    with patch("app.web.runtime.warm_transcriber", return_value={"warmed": True, "provider": "local-whisper"}):
        warm_response = app_client.post("/api/transcribe/warmup")
    assert warm_response.status_code == 200
    assert warm_response.get_json()["warmed"] is True

    with patch("app.web.runtime.resolve_ollama_model", return_value="llama3.1:8b"), patch(
        "app.web.runtime.warm_ollama_model",
        return_value={"ok": True},
    ):
        ollama_response = app_client.post("/api/ollama/warmup", json={"model": "llama3.1:8b"})
    assert ollama_response.status_code == 200
    assert ollama_response.get_json()["model"] == "llama3.1:8b"

    with patch("app.web.runtime.warm_browser", return_value={"warmed": True, "provider": "chatgpt", "url": "https://chatgpt.com/"}):
        browser_response = app_client.post("/api/browser/warmup")
    assert browser_response.status_code == 200
    assert browser_response.get_json()["warmed"] is True

    with patch("app.web.runtime.transcribe_audio_file", return_value="test transcript"):
        transcribe_response = app_client.post(
            "/api/transcribe",
            data={"audio": (io.BytesIO(b"RIFFtestWAVE"), "sample.wav")},
            content_type="multipart/form-data",
        )
    assert transcribe_response.status_code == 200
    assert transcribe_response.get_json()["text"] == "test transcript"


def test_send_stream_output_is_valid_ndjson(app_client):
    with patch("app.web.messages.resolve_ollama_model", return_value="llama3.1:8b"), patch(
        "app.web.messages.stream_prompt_response",
        return_value=iter(["chatgpt answer"]),
    ), patch(
        "app.web.messages.stream_ollama_response",
        return_value=iter(["ollama answer"]),
    ):
        response = app_client.post(
            "/api/send",
            json={"message": "ndjson", "ollama_model": "llama3.1:8b"},
        )
        lines = [line for line in response.get_data(as_text=True).splitlines() if line.strip()]

    parsed = [json.loads(line) for line in lines]
    assert parsed[0]["type"] == "start"
    assert parsed[-1]["type"] == "complete"


def test_send_route_degrades_to_chatgpt_when_ollama_is_unavailable(app_client):
    shell_payload = {
        "status": {
            "chatgpt": {"connected": True, "message": "Attached to Brave"},
            "ollama": {"connected": False, "message": "Ollama not reachable at http://127.0.0.1:11434"},
        },
        "ollama_models": [],
        "default_ollama_model": "",
    }

    with patch("app.web.messages.build_shell_payload", return_value=shell_payload), patch(
        "app.web.messages.stream_prompt_response",
        return_value=iter(["chatgpt only answer"]),
    ) as chatgpt_stream, patch(
        "app.web.messages.stream_ollama_response",
    ) as ollama_stream:
        response = app_client.post("/api/send", json={"message": "chatgpt only"})
        lines = [json.loads(line) for line in response.get_data(as_text=True).splitlines() if line.strip()]

    assert response.status_code == 200
    assert chatgpt_stream.called is True
    ollama_stream.assert_not_called()
    assert any(line["type"] == "provider_final" and line["provider"] == "chatgpt" for line in lines)
    assert any(
        line["type"] == "provider_error"
        and line["provider"] == "ollama"
        and "Ollama not reachable" in line["error"]
        for line in lines
    )


def test_send_route_degrades_to_ollama_when_chatgpt_is_unavailable(app_client):
    shell_payload = {
        "status": {
            "chatgpt": {"connected": False, "message": "Brave is not exposing remote debugging on port 9222"},
            "ollama": {"connected": True, "message": "Ollama ready (1 model)"},
        },
        "ollama_models": [{"name": "llama3.1:8b"}],
        "default_ollama_model": "llama3.1:8b",
    }

    with patch("app.web.messages.build_shell_payload", return_value=shell_payload), patch(
        "app.web.messages.resolve_ollama_model",
        return_value="llama3.1:8b",
    ), patch(
        "app.web.messages.stream_ollama_response",
        return_value=iter(["ollama only answer"]),
    ) as ollama_stream, patch(
        "app.web.messages.stream_prompt_response",
    ) as chatgpt_stream:
        response = app_client.post("/api/send", json={"message": "ollama only", "ollama_model": "llama3.1:8b"})
        lines = [json.loads(line) for line in response.get_data(as_text=True).splitlines() if line.strip()]

    assert response.status_code == 200
    assert ollama_stream.called is True
    chatgpt_stream.assert_not_called()
    assert any(line["type"] == "provider_final" and line["provider"] == "ollama" for line in lines)
    assert any(
        line["type"] == "provider_error"
        and line["provider"] == "chatgpt"
        and "remote debugging" in line["error"]
        for line in lines
    )


def test_send_route_returns_503_when_no_provider_is_available(app_client):
    shell_payload = {
        "status": {
            "chatgpt": {"connected": False, "message": "Brave is not exposing remote debugging on port 9222"},
            "ollama": {"connected": False, "message": "Ollama not reachable at http://127.0.0.1:11434"},
        },
        "ollama_models": [],
        "default_ollama_model": "",
    }

    with patch("app.web.messages.build_shell_payload", return_value=shell_payload):
        response = app_client.post("/api/send", json={"message": "nobody home"})

    payload = response.get_json()
    assert response.status_code == 503
    assert "Neither ChatGPT nor Ollama is ready." in payload["error"]
