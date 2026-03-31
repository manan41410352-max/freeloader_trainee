from __future__ import annotations

from flask import Flask, jsonify, request

from app.web.helpers import build_shell_payload
from app.web.services import WebServices


def register_chat_routes(flask_app: Flask, services: WebServices) -> None:
    """Register chat history CRUD routes."""

    @flask_app.get("/api/chats")
    def list_chats():
        search_query = (request.args.get("q") or "").strip()
        try:
            search_limit = max(1, min(int(request.args.get("limit", "80")), 250))
        except ValueError:
            search_limit = 80
        try:
            search_min_score = max(0.0, min(float(request.args.get("min_score", "1.8")), 12.0))
        except ValueError:
            search_min_score = 1.8

        payload = build_shell_payload(services)
        payload["chats"] = services.store.list_chats(
            query=search_query,
            limit=search_limit,
            min_score=search_min_score,
        )
        payload["search_query"] = search_query
        payload["search_meta"] = {
            "limit": search_limit,
            "min_score": search_min_score,
            "mode": "fuzzy",
        }
        return jsonify(payload)

    @flask_app.get("/api/chats/<chat_id>")
    def get_chat(chat_id: str):
        chat = services.store.get_chat(chat_id)
        if chat is None:
            return jsonify({"error": "Chat not found."}), 404

        payload = build_shell_payload(services)
        payload["chat"] = chat
        return jsonify(payload)

    @flask_app.post("/api/chats")
    def create_chat():
        payload = request.get_json(silent=True) or {}
        title = (payload.get("title") or "New Chat").strip() or "New Chat"
        chat = services.store.create_chat(title=title)

        response_payload = build_shell_payload(services)
        response_payload["chat"] = chat
        return jsonify(response_payload), 201

    @flask_app.delete("/api/chats/<chat_id>")
    def delete_chat(chat_id: str):
        if not services.store.delete_chat(chat_id):
            return jsonify({"error": "Chat not found."}), 404

        payload = build_shell_payload(services)
        payload["deleted"] = True
        payload["chat_id"] = chat_id
        return jsonify(payload)
