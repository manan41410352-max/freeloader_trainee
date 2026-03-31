from __future__ import annotations

import copy
import json
import os
import re
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from app.attachments import build_ollama_user_content


STORE_VERSION = 3
RESPONSE_ORDER = ["chatgpt", "ollama"]
PROVIDER_PRIORITY = {provider: index for index, provider in enumerate(RESPONSE_ORDER)}
SEARCH_WORD_RE = re.compile(r"[a-z0-9]+")
SOURCE_WEIGHTS = {
    "title": 1.35,
    "prompt": 1.18,
    "chatgpt": 1.04,
    "ollama": 1.0,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _snippet(text: str, limit: int = 80) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_search_text(text: str) -> str:
    return " ".join(SEARCH_WORD_RE.findall((text or "").casefold()))


def _search_tokens(text: str) -> list[str]:
    normalized_text = _normalize_search_text(text)
    return normalized_text.split() if normalized_text else []


def _compact_attachment_metadata(attachments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for attachment in attachments:
        compact.append(
            {
                "name": str(attachment.get("name") or ""),
                "size_bytes": max(0, _safe_int(attachment.get("size_bytes")) or 0),
                "content_type": str(attachment.get("content_type") or ""),
                "ollama_supported": bool(attachment.get("ollama_supported")),
                "ollama_text_chars": max(0, _safe_int(attachment.get("ollama_text_chars")) or 0),
                "ollama_truncated": bool(attachment.get("ollama_truncated")),
                "ollama_error": str(attachment.get("ollama_error") or ""),
            }
        )
    return compact


def _normalize_attachments(raw_attachments: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw_attachment in list(raw_attachments or []):
        if not isinstance(raw_attachment, dict):
            continue

        name = _snippet(
            str(
                raw_attachment.get("name")
                or raw_attachment.get("filename")
                or raw_attachment.get("stored_name")
                or ""
            ),
            limit=120,
        )
        if not name:
            continue

        normalized.append(
            {
                "name": name,
                "size_bytes": max(0, _safe_int(raw_attachment.get("size_bytes") or raw_attachment.get("size")) or 0),
                "content_type": str(raw_attachment.get("content_type") or raw_attachment.get("mime_type") or ""),
                "ollama_supported": bool(raw_attachment.get("ollama_supported")),
                "ollama_source_type": str(raw_attachment.get("ollama_source_type") or ""),
                "ollama_text": str(raw_attachment.get("ollama_text") or ""),
                "ollama_text_chars": max(0, _safe_int(raw_attachment.get("ollama_text_chars")) or 0),
                "ollama_truncated": bool(raw_attachment.get("ollama_truncated")),
                "ollama_error": str(raw_attachment.get("ollama_error") or ""),
            }
        )
    return normalized


def _response_sort_key(message: dict) -> tuple[int, str, str, int]:
    provider = str(message.get("provider") or "")
    model_name = str(message.get("model_name") or "")
    created_at = str(message.get("created_at") or "")
    message_id = _safe_int(message.get("id")) or 0
    return (PROVIDER_PRIORITY.get(provider, 99), model_name, created_at, message_id)


class ChatStore:
    """JSON-backed local storage with training-friendly turn ordering."""

    def __init__(self, store_path: Path) -> None:
        requested_path = Path(store_path)
        if requested_path.suffix.lower() == ".json":
            self.json_path = requested_path
            self.legacy_sqlite_path = requested_path.with_suffix(".db")
        else:
            self.json_path = requested_path.with_suffix(".json")
            self.legacy_sqlite_path = requested_path

        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._state = self._load_state()

    def _empty_state(self) -> dict[str, Any]:
        return {
            "format": "dual_chat_store",
            "version": STORE_VERSION,
            "response_order": RESPONSE_ORDER,
            "next_message_id": 1,
            "chats": [],
        }

    def _load_state(self) -> dict[str, Any]:
        if self.json_path.exists():
            raw_state = self._read_json_state()
            state = self._normalize_state(raw_state)
            legacy_merged = False
            if self.legacy_sqlite_path.exists() and self.legacy_sqlite_path.suffix.lower() == ".db":
                legacy_state = self._migrate_sqlite(self.legacy_sqlite_path)
                state, legacy_merged = self._merge_legacy_state(state, legacy_state)

            if _safe_int(raw_state.get("version")) != STORE_VERSION or legacy_merged:
                self._write_state(state)
            return state

        if self.legacy_sqlite_path.exists() and self.legacy_sqlite_path.suffix.lower() == ".db":
            state = self._migrate_sqlite(self.legacy_sqlite_path)
            self._write_state(state)
            return state

        state = self._empty_state()
        self._write_state(state)
        return state

    def _merge_legacy_state(
        self,
        current_state: dict[str, Any],
        legacy_state: dict[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        changed = False
        chats_by_id = {
            str(chat.get("id") or ""): chat
            for chat in current_state.get("chats", [])
            if str(chat.get("id") or "")
        }

        for legacy_chat in legacy_state.get("chats", []):
            legacy_chat_id = str(legacy_chat.get("id") or "")
            if not legacy_chat_id:
                continue

            existing_chat = chats_by_id.get(legacy_chat_id)
            if existing_chat is None:
                current_state["chats"].append(copy.deepcopy(legacy_chat))
                chats_by_id[legacy_chat_id] = current_state["chats"][-1]
                changed = True
                continue

            if self._merge_legacy_chat(existing_chat, legacy_chat):
                changed = True

        current_state["next_message_id"] = max(
            _safe_int(current_state.get("next_message_id")) or 1,
            _safe_int(legacy_state.get("next_message_id")) or 1,
        )

        return current_state, changed

    def _merge_legacy_chat(self, current_chat: dict[str, Any], legacy_chat: dict[str, Any]) -> bool:
        changed = False

        if current_chat.get("title") == "New Chat" and legacy_chat.get("title"):
            current_chat["title"] = legacy_chat["title"]
            changed = True

        current_chat["created_at"] = min(
            str(current_chat.get("created_at") or _utc_now()),
            str(legacy_chat.get("created_at") or _utc_now()),
        )
        current_chat["updated_at"] = max(
            str(current_chat.get("updated_at") or current_chat["created_at"]),
            str(legacy_chat.get("updated_at") or current_chat["created_at"]),
        )

        current_turns = current_chat.setdefault("turns", [])
        turns_by_id = {
            str(turn.get("id") or ""): turn
            for turn in current_turns
            if str(turn.get("id") or "")
        }

        for legacy_turn in legacy_chat.get("turns", []):
            legacy_turn_id = str(legacy_turn.get("id") or "")
            if not legacy_turn_id:
                continue

            existing_turn = turns_by_id.get(legacy_turn_id)
            if existing_turn is None:
                current_turns.append(copy.deepcopy(legacy_turn))
                turns_by_id[legacy_turn_id] = current_turns[-1]
                changed = True
                continue

            if self._merge_legacy_turn(existing_turn, legacy_turn):
                changed = True

        if changed:
            current_turns.sort(
                key=lambda turn: (
                    str(turn.get("created_at") or ""),
                    str(turn.get("id") or ""),
                )
            )

        return changed

    def _merge_legacy_turn(self, current_turn: dict[str, Any], legacy_turn: dict[str, Any]) -> bool:
        changed = False

        if current_turn.get("prompt") is None and legacy_turn.get("prompt") is not None:
            current_turn["prompt"] = copy.deepcopy(legacy_turn["prompt"])
            changed = True

        merged_responses = self._ordered_responses(
            [
                *list(current_turn.get("responses") or []),
                *list(legacy_turn.get("responses") or []),
            ]
        )
        if merged_responses != list(current_turn.get("responses") or []):
            current_turn["responses"] = merged_responses
            changed = True

        current_turn["created_at"] = min(
            str(current_turn.get("created_at") or _utc_now()),
            str(legacy_turn.get("created_at") or current_turn.get("created_at") or _utc_now()),
        )
        return changed

    def _read_json_state(self) -> dict[str, Any]:
        raw_text = self.json_path.read_text(encoding="utf-8").strip()
        if not raw_text:
            return self._empty_state()
        return json.loads(raw_text)

    def _write_state(self, state: dict[str, Any]) -> None:
        payload = self._make_persisted_state(state)
        temp_path = self.json_path.with_suffix(f"{self.json_path.suffix}.tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temp_path, self.json_path)

    def _save_locked(self) -> None:
        self._write_state(self._state)

    def _make_persisted_state(self, state: dict[str, Any]) -> dict[str, Any]:
        chats_payload = [self._serialize_chat(chat) for chat in state.get("chats", [])]
        preference_pairs = self._build_all_dpo_examples(state.get("chats", []))
        return {
            "format": "dual_chat_store",
            "version": STORE_VERSION,
            "response_order": RESPONSE_ORDER,
            "next_message_id": max(1, _safe_int(state.get("next_message_id")) or 1),
            "training": {
                "format": "unsloth_dpo_v1",
                "description": (
                    "Hidden preference pairs for local fine-tuning. "
                    "ChatGPT is stored as chosen and Ollama is stored as rejected."
                ),
                "pair_count": len(preference_pairs),
                "preference_pairs": preference_pairs,
            },
            "chats": chats_payload,
        }

    def _build_all_dpo_examples(self, chats: list[dict[str, Any]]) -> list[dict[str, Any]]:
        examples: list[dict[str, Any]] = []
        for chat in chats:
            examples.extend(self._build_chat_dpo_examples(chat))
        return examples

    def _build_chat_dpo_examples(self, chat: dict[str, Any]) -> list[dict[str, Any]]:
        examples: list[dict[str, Any]] = []
        preferred_context_messages: list[dict[str, str]] = []

        for turn in chat.get("turns", []):
            prompt = turn.get("prompt")
            if not isinstance(prompt, dict):
                continue

            prompt_text = str(prompt.get("content") or "").strip()
            if not prompt_text:
                continue

            attachments = _normalize_attachments(prompt.get("attachments") or [])
            training_prompt = build_ollama_user_content(prompt_text, attachments)
            prompt_messages = [copy.deepcopy(message) for message in preferred_context_messages]
            prompt_messages.append({"role": "user", "content": training_prompt})

            responses = self._ordered_responses(turn.get("responses") or [])
            chosen = next(
                (
                    response for response in responses
                    if str(response.get("provider") or "") == "chatgpt" and str(response.get("content") or "").strip()
                ),
                None,
            )
            rejected_candidates = [
                response for response in responses
                if str(response.get("provider") or "") == "ollama" and str(response.get("content") or "").strip()
            ]

            if chosen is not None and rejected_candidates:
                for rejected in rejected_candidates:
                    rejected_model = str(rejected.get("model_name") or "ollama")
                    rejected_slug = re.sub(r"[^a-z0-9]+", "-", rejected_model.casefold()).strip("-") or "ollama"
                    examples.append(
                        {
                            "id": f"{chat['id']}:{turn['id']}:{rejected_slug}",
                            "chat_id": chat["id"],
                            "chat_title": chat["title"],
                            "turn_id": turn["id"],
                            "created_at": str(turn.get("created_at") or prompt.get("created_at") or _utc_now()),
                            "source": "dual_chat_browser_vs_ollama",
                            "preference_type": "dpo",
                            "prompt": training_prompt,
                            "prompt_user": prompt_text,
                            "prompt_messages": prompt_messages,
                            "chosen": str(chosen.get("content") or "").strip(),
                            "rejected": str(rejected.get("content") or "").strip(),
                            "chosen_provider": "chatgpt",
                            "chosen_model": str(chosen.get("model_name") or "ChatGPT"),
                            "rejected_provider": "ollama",
                            "rejected_model": rejected_model,
                            "chosen_message_id": _safe_int(chosen.get("id")),
                            "rejected_message_id": _safe_int(rejected.get("id")),
                            "has_attachments": bool(attachments),
                            "attachments": _compact_attachment_metadata(attachments),
                        }
                    )

            preferred_context_messages.append({"role": "user", "content": training_prompt})
            if chosen is not None:
                preferred_context_messages.append(
                    {"role": "assistant", "content": str(chosen.get("content") or "").strip()}
                )

        return examples

    def _serialize_chat(self, chat: dict[str, Any]) -> dict[str, Any]:
        turns_payload: list[dict[str, Any]] = []
        for turn in chat.get("turns", []):
            responses = self._ordered_responses(turn.get("responses") or [])
            turns_payload.append(
                {
                    "id": turn["id"],
                    "created_at": turn["created_at"],
                    "prompt": copy.deepcopy(turn.get("prompt")),
                    "responses": copy.deepcopy(responses),
                }
            )

        return {
            "id": chat["id"],
            "title": chat["title"],
            "created_at": chat["created_at"],
            "updated_at": chat["updated_at"],
            # Keep a flattened training-ready sequence alongside turns.
            "messages": self._flatten_messages(chat),
            "turns": turns_payload,
        }

    def _normalize_state(self, raw_state: dict[str, Any]) -> dict[str, Any]:
        normalized_state = self._empty_state()
        max_message_id = 0

        for raw_chat in raw_state.get("chats", []):
            chat_payload, chat_max_id = self._normalize_chat(raw_chat)
            normalized_state["chats"].append(chat_payload)
            max_message_id = max(max_message_id, chat_max_id)

        normalized_state["next_message_id"] = max(
            max_message_id + 1,
            _safe_int(raw_state.get("next_message_id")) or 1,
        )
        return normalized_state

    def _normalize_chat(self, raw_chat: dict[str, Any]) -> tuple[dict[str, Any], int]:
        chat_id = str(raw_chat.get("id") or uuid.uuid4().hex)
        created_at = str(raw_chat.get("created_at") or _utc_now())
        updated_at = str(raw_chat.get("updated_at") or created_at)
        title = _snippet(str(raw_chat.get("title") or "New Chat"), limit=60) or "New Chat"

        turns_payload: list[dict[str, Any]] = []
        max_message_id = 0
        for raw_turn in raw_chat.get("turns", []):
            turn_payload, turn_max_id = self._normalize_turn(raw_turn)
            turns_payload.append(turn_payload)
            max_message_id = max(max_message_id, turn_max_id)

        return (
            {
                "id": chat_id,
                "title": title,
                "created_at": created_at,
                "updated_at": updated_at,
                "turns": turns_payload,
            },
            max_message_id,
        )

    def _normalize_turn(self, raw_turn: dict[str, Any]) -> tuple[dict[str, Any], int]:
        turn_id = str(raw_turn.get("id") or uuid.uuid4().hex)
        prompt_payload, prompt_id = self._normalize_message(
            raw_turn.get("prompt"),
            turn_id=turn_id,
            default_role="user",
            default_provider="user",
        )

        responses: list[dict[str, Any]] = []
        max_message_id = prompt_id

        raw_responses: list[tuple[dict[str, Any], str]] = [
            (raw_response, str((raw_response or {}).get("provider") or "chatgpt"))
            for raw_response in list(raw_turn.get("responses") or [])
            if isinstance(raw_response, dict)
        ]
        if isinstance(raw_turn.get("chatgpt"), dict):
            raw_responses.append((raw_turn["chatgpt"], "chatgpt"))
        if isinstance(raw_turn.get("ollama"), dict):
            raw_responses.extend(
                (raw_response, "ollama")
                for raw_response in raw_turn["ollama"].values()
                if isinstance(raw_response, dict)
            )

        for raw_response, default_provider in raw_responses:
            response_payload, response_id = self._normalize_message(
                raw_response,
                turn_id=turn_id,
                default_role="assistant",
                default_provider=default_provider,
            )
            if response_payload is not None:
                responses.append(response_payload)
                max_message_id = max(max_message_id, response_id)

        created_at = str(
            raw_turn.get("created_at")
            or (prompt_payload or {}).get("created_at")
            or (responses[0] if responses else {}).get("created_at")
            or _utc_now()
        )

        return (
            {
                "id": turn_id,
                "created_at": created_at,
                "prompt": prompt_payload,
                "responses": self._ordered_responses(responses),
            },
            max_message_id,
        )

    def _normalize_message(
        self,
        raw_message: dict[str, Any] | None,
        *,
        turn_id: str,
        default_role: str,
        default_provider: str,
    ) -> tuple[dict[str, Any] | None, int]:
        if not isinstance(raw_message, dict):
            return None, 0

        message_id = _safe_int(raw_message.get("id"))
        content = str(raw_message.get("content") or "").strip()
        if not content:
            return None, message_id or 0

        role = str(raw_message.get("role") or default_role)
        provider = str(raw_message.get("provider") or default_provider)
        model_name = raw_message.get("model_name")

        if role == "user":
            provider = "user"
            model_name = None
        elif provider == "chatgpt" and not model_name:
            model_name = "ChatGPT"

        payload = {
            "id": message_id,
            "role": role,
            "provider": provider,
            "model_name": model_name,
            "turn_id": str(raw_message.get("turn_id") or turn_id),
            "content": content,
            "created_at": str(raw_message.get("created_at") or _utc_now()),
        }
        attachments = _normalize_attachments(raw_message.get("attachments") or [])
        if attachments:
            payload["attachments"] = attachments
        return payload, message_id or 0

    def _ordered_responses(self, responses: list[dict[str, Any]]) -> list[dict[str, Any]]:
        latest_by_key: dict[tuple[str, str], dict[str, Any]] = {}
        for response in responses:
            provider = str(response.get("provider") or "")
            model_name = str(response.get("model_name") or "")
            dedupe_key = (provider, model_name)
            existing_response = latest_by_key.get(dedupe_key)
            if existing_response is None or _response_sort_key(response) > _response_sort_key(existing_response):
                latest_by_key[dedupe_key] = response

        return [
            copy.deepcopy(response)
            for response in sorted(latest_by_key.values(), key=_response_sort_key)
        ]

    def _flatten_messages(self, chat: dict[str, Any]) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        for turn in chat.get("turns", []):
            if turn.get("prompt") is not None:
                messages.append(copy.deepcopy(turn["prompt"]))
            for response in self._ordered_responses(turn.get("responses") or []):
                messages.append(copy.deepcopy(response))
        return messages

    def _present_turn(self, turn: dict[str, Any]) -> dict[str, Any]:
        responses = self._ordered_responses(turn.get("responses") or [])
        chatgpt_message = None
        ollama_messages: dict[str, dict[str, Any]] = {}

        for response in responses:
            provider = str(response.get("provider") or "")
            if provider == "chatgpt" and chatgpt_message is None:
                chatgpt_message = copy.deepcopy(response)
            elif provider == "ollama":
                model_name = str(response.get("model_name") or "default")
                ollama_messages[model_name] = copy.deepcopy(response)

        return {
            "id": turn["id"],
            "created_at": turn["created_at"],
            "prompt": copy.deepcopy(turn.get("prompt")),
            "responses": copy.deepcopy(responses),
            "chatgpt": chatgpt_message,
            "ollama": ollama_messages,
        }

    def _present_chat(self, chat: dict[str, Any]) -> dict[str, Any]:
        turns = [self._present_turn(turn) for turn in chat.get("turns", [])]
        return {
            "id": chat["id"],
            "title": chat["title"],
            "created_at": chat["created_at"],
            "updated_at": chat["updated_at"],
            "messages": self._flatten_messages(chat),
            "turns": turns,
        }

    def _find_chat_locked(self, chat_id: str) -> dict[str, Any] | None:
        for chat in self._state.get("chats", []):
            if chat["id"] == chat_id:
                return chat
        return None

    def _find_turn_locked(self, chat: dict[str, Any], turn_id: str) -> dict[str, Any] | None:
        for turn in chat.get("turns", []):
            if turn["id"] == turn_id:
                return turn
        return None

    def _next_message_id_locked(self) -> int:
        next_message_id = max(1, _safe_int(self._state.get("next_message_id")) or 1)
        self._state["next_message_id"] = next_message_id + 1
        return next_message_id

    def _iter_search_candidates(self, chat: dict[str, Any]) -> list[dict[str, str]]:
        candidates = [
            {
                "source": "title",
                "label": "Title",
                "text": str(chat.get("title") or ""),
                "search_text": str(chat.get("title") or ""),
            }
        ]

        for turn in chat.get("turns", []):
            prompt = turn.get("prompt")
            if prompt and prompt.get("content"):
                candidates.append(
                    {
                        "source": "prompt",
                        "label": "Prompt",
                        "text": str(prompt.get("content") or ""),
                        "search_text": f"prompt {prompt.get('content') or ''}",
                    }
                )

            for response in turn.get("responses", []):
                provider = str(response.get("provider") or "")
                if provider == "chatgpt":
                    label = "ChatGPT"
                    source = "chatgpt"
                    search_text = f"chatgpt assistant browser {response.get('content') or ''}"
                elif provider == "ollama":
                    label = str(response.get("model_name") or "Local model")
                    source = "ollama"
                    search_text = f"local model ollama {label} {response.get('content') or ''}"
                else:
                    label = provider or "Message"
                    source = provider or "message"
                    search_text = f"{label} {provider} {response.get('content') or ''}"

                candidates.append(
                    {
                        "source": source,
                        "label": label,
                        "text": str(response.get("content") or ""),
                        "search_text": search_text,
                    }
                )

        return candidates

    def _make_search_excerpt(self, text: str, query_tokens: list[str], limit: int = 120) -> str:
        clean_text = " ".join((text or "").split())
        if len(clean_text) <= limit:
            return clean_text

        lower_text = clean_text.casefold()
        token_positions = [
            lower_text.find(token)
            for token in query_tokens
            if token and lower_text.find(token) >= 0
        ]
        start = 0
        if token_positions:
            start = max(0, min(token_positions) - (limit // 3))

        end = min(len(clean_text), start + limit)
        excerpt = clean_text[start:end].strip()
        if start > 0:
            excerpt = "..." + excerpt
        if end < len(clean_text):
            excerpt += "..."
        return excerpt

    def _fuzzy_token_score(self, query_tokens: list[str], candidate_tokens: list[str]) -> float:
        if not query_tokens or not candidate_tokens:
            return 0.0

        total_score = 0.0
        for query_token in query_tokens:
            best_score = max(
                SequenceMatcher(None, query_token, candidate_token).ratio()
                for candidate_token in candidate_tokens
            )
            total_score += best_score

        return total_score / len(query_tokens)

    def _score_search_candidate(
        self,
        query: str,
        candidate: dict[str, str],
    ) -> dict[str, Any] | None:
        candidate_text = " ".join((candidate.get("text") or "").split())
        if not candidate_text:
            return None

        query_text = _normalize_search_text(query)
        query_tokens = _search_tokens(query)
        if not query_text or not query_tokens:
            return None

        candidate_search_text = " ".join((candidate.get("search_text") or candidate_text).split())
        candidate_text_normalized = _normalize_search_text(candidate_search_text)
        if not candidate_text_normalized:
            return None

        candidate_tokens = candidate_text_normalized.split()
        query_compact = "".join(query_tokens)
        candidate_compact = "".join(candidate_tokens)

        exact_match = query_text == candidate_text_normalized
        contains_phrase = query_text in candidate_text_normalized
        starts_with_query = candidate_text_normalized.startswith(query_text)
        compact_contains = bool(query_compact) and query_compact in candidate_compact
        exact_token_hits = sum(1 for token in query_tokens if token in candidate_tokens)
        token_coverage = exact_token_hits / len(query_tokens)
        fuzzy_token_coverage = self._fuzzy_token_score(query_tokens, candidate_tokens)
        sequence_ratio = SequenceMatcher(None, query_text, candidate_text_normalized).ratio()
        compact_ratio = SequenceMatcher(None, query_compact, candidate_compact).ratio()

        source_weight = SOURCE_WEIGHTS.get(candidate.get("source") or "", 1.0)
        score = (
            (4.8 if exact_match else 0.0)
            + (3.1 if contains_phrase else 0.0)
            + (1.1 if starts_with_query else 0.0)
            + (2.2 if compact_contains else 0.0)
            + (token_coverage * 2.8)
            + (fuzzy_token_coverage * 2.0)
            + (sequence_ratio * 0.85)
            + (compact_ratio * 0.75)
        ) * source_weight

        likely_match = (
            exact_match
            or contains_phrase
            or compact_contains
            or token_coverage >= 0.34
            or fuzzy_token_coverage >= 0.84
            or compact_ratio >= 0.82
            or score >= 2.2
        )
        if not likely_match:
            return None

        return {
            "score": score,
            "label": candidate.get("label") or "Match",
            "source": candidate.get("source") or "message",
            "excerpt": self._make_search_excerpt(candidate_text, query_tokens),
        }

    def _best_chat_match(
        self,
        chat: dict[str, Any],
        query: str,
        *,
        min_score: float,
    ) -> dict[str, Any] | None:
        if not query.strip():
            return None

        best_match: dict[str, Any] | None = None
        for candidate in self._iter_search_candidates(chat):
            candidate_match = self._score_search_candidate(query, candidate)
            if candidate_match is None:
                continue
            if best_match is None or candidate_match["score"] > best_match["score"]:
                best_match = candidate_match

        if best_match is None:
            return None

        adaptive_min_score = min_score
        query_tokens = _search_tokens(query)
        if len(query_tokens) == 1 and len(query_tokens[0]) <= 3:
            adaptive_min_score += 0.35

        if best_match["score"] < adaptive_min_score:
            return None

        return best_match

    def _migrate_sqlite(self, db_path: Path) -> dict[str, Any]:
        state = self._empty_state()
        max_message_id = 0

        connection = sqlite3.connect(db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        try:
            chat_rows = connection.execute(
                """
                SELECT id, title, created_at, updated_at
                FROM chats
                ORDER BY created_at ASC, id ASC
                """
            ).fetchall()

            for chat_row in chat_rows:
                message_rows = connection.execute(
                    """
                    SELECT id, role, provider, model_name, turn_id, content, created_at
                    FROM messages
                    WHERE chat_id = ?
                    ORDER BY id ASC
                    """,
                    (chat_row["id"],),
                ).fetchall()

                turns_payload: list[dict[str, Any]] = []
                turn_lookup: dict[str, dict[str, Any]] = {}
                active_legacy_turn: dict[str, Any] | None = None
                for row in message_rows:
                    row_id = _safe_int(row["id"]) or 0
                    max_message_id = max(max_message_id, row_id)
                    explicit_turn_id = row["turn_id"] or ""
                    if explicit_turn_id:
                        turn_id = explicit_turn_id
                    elif row["role"] == "user":
                        turn_id = f"legacy-turn-{row_id}"
                    elif active_legacy_turn is not None:
                        turn_id = active_legacy_turn["id"]
                    else:
                        turn_id = f"legacy-turn-{row_id}"

                    turn = turn_lookup.get(turn_id)
                    if turn is None:
                        turn = {
                            "id": turn_id,
                            "created_at": row["created_at"],
                            "prompt": None,
                            "responses": [],
                        }
                        turn_lookup[turn_id] = turn
                        turns_payload.append(turn)

                    if row["role"] == "user":
                        active_legacy_turn = turn
                    elif explicit_turn_id:
                        active_legacy_turn = turn_lookup.get(explicit_turn_id) or active_legacy_turn

                    provider = row["provider"] or ("user" if row["role"] == "user" else "chatgpt")
                    model_name = row["model_name"]
                    if row["role"] != "user" and provider == "chatgpt" and not model_name:
                        model_name = "ChatGPT"

                    message_payload = {
                        "id": row_id,
                        "role": row["role"],
                        "provider": provider,
                        "model_name": model_name,
                        "turn_id": turn_id,
                        "content": row["content"],
                        "created_at": row["created_at"],
                    }

                    if row["role"] == "user":
                        turn["prompt"] = message_payload
                    else:
                        turn["responses"].append(message_payload)

                for turn in turns_payload:
                    turn["responses"] = self._ordered_responses(turn.get("responses") or [])

                state["chats"].append(
                    {
                        "id": chat_row["id"],
                        "title": _snippet(chat_row["title"], limit=60) or "New Chat",
                        "created_at": chat_row["created_at"],
                        "updated_at": chat_row["updated_at"],
                        "turns": turns_payload,
                    }
                )
        finally:
            connection.close()

        state["next_message_id"] = max_message_id + 1
        return state

    def list_chats(
        self,
        query: str | None = None,
        *,
        limit: int = 80,
        min_score: float = 1.8,
    ) -> list[dict]:
        search_text = (query or "").strip()
        safe_limit = max(1, min(_safe_int(limit) or 80, 250))
        safe_min_score = max(0.0, min(_safe_float(min_score, 1.8), 12.0))

        with self._lock:
            payload: list[dict[str, Any]] = []
            chats = list(self._state.get("chats", []))

            if search_text:
                ranked_chats: list[tuple[float, str, dict[str, Any], dict[str, Any]]] = []
                for chat in chats:
                    best_match = self._best_chat_match(chat, search_text, min_score=safe_min_score)
                    if best_match is None:
                        continue
                    ranked_chats.append((best_match["score"], chat["updated_at"], chat, best_match))

                ranked_chats.sort(key=lambda item: (item[0], item[1]), reverse=True)
                selected = ranked_chats[:safe_limit]

                for _, _, chat, best_match in selected:
                    messages = self._flatten_messages(chat)
                    payload.append(
                        {
                            "id": chat["id"],
                            "title": chat["title"],
                            "preview": best_match["excerpt"] or _snippet(chat["title"]),
                            "last_message_role": (messages[-1] if messages else {}).get("role", ""),
                            "message_count": len(messages),
                            "created_at": chat["created_at"],
                            "updated_at": chat["updated_at"],
                            "search_score": round(best_match["score"], 3),
                            "search_source": best_match["source"],
                            "search_label": best_match["label"],
                        }
                    )

                return payload

            sorted_chats = sorted(chats, key=lambda chat: chat["updated_at"], reverse=True)[:safe_limit]

            for chat in sorted_chats:
                messages = self._flatten_messages(chat)
                last_message = messages[-1] if messages else {}
                payload.append(
                    {
                        "id": chat["id"],
                        "title": chat["title"],
                        "preview": _snippet(last_message.get("content") or chat["title"]),
                        "last_message_role": last_message.get("role", ""),
                        "message_count": len(messages),
                        "created_at": chat["created_at"],
                        "updated_at": chat["updated_at"],
                    }
                )

            return payload

    def create_chat(self, title: str = "New Chat") -> dict:
        chat_id = uuid.uuid4().hex
        now = _utc_now()
        clean_title = _snippet(title or "New Chat", limit=60) or "New Chat"

        with self._lock:
            self._state["chats"].append(
                {
                    "id": chat_id,
                    "title": clean_title,
                    "created_at": now,
                    "updated_at": now,
                    "turns": [],
                }
            )
            self._save_locked()
            chat = self._find_chat_locked(chat_id)
            if chat is None:
                raise RuntimeError("Failed to create chat.")
            return self._present_chat(chat)

    def get_chat(self, chat_id: str) -> dict | None:
        with self._lock:
            chat = self._find_chat_locked(chat_id)
            if chat is None:
                return None
            return self._present_chat(chat)

    def add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        *,
        provider: str | None = None,
        model_name: str | None = None,
        turn_id: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict:
        now = _utc_now()
        clean_content = content.strip()
        if not clean_content:
            raise ValueError("Message content cannot be empty.")

        resolved_provider = provider or ("user" if role == "user" else "chatgpt")
        resolved_turn_id = turn_id or uuid.uuid4().hex

        with self._lock:
            chat = self._find_chat_locked(chat_id)
            if chat is None:
                raise ValueError("Chat not found.")

            message_payload = {
                "id": self._next_message_id_locked(),
                "chat_id": chat_id,
                "role": role,
                "provider": resolved_provider,
                "model_name": model_name if role != "user" else None,
                "turn_id": resolved_turn_id,
                "content": clean_content,
                "created_at": now,
            }
            normalized_attachments = _normalize_attachments(attachments or [])
            if normalized_attachments:
                message_payload["attachments"] = normalized_attachments

            if role != "user" and message_payload["provider"] == "chatgpt" and not message_payload["model_name"]:
                message_payload["model_name"] = "ChatGPT"

            turn = self._find_turn_locked(chat, resolved_turn_id)
            if turn is None:
                turn = {
                    "id": resolved_turn_id,
                    "created_at": now,
                    "prompt": None,
                    "responses": [],
                }
                chat["turns"].append(turn)

            if role == "user":
                turn["prompt"] = {key: value for key, value in message_payload.items() if key != "chat_id"}
                if chat["title"] == "New Chat":
                    chat["title"] = _snippet(clean_content, limit=60) or "New Chat"
            else:
                response_payload = {key: value for key, value in message_payload.items() if key != "chat_id"}
                replaced = False
                for index, existing_response in enumerate(turn["responses"]):
                    same_provider = existing_response.get("provider") == response_payload["provider"]
                    same_model = (existing_response.get("model_name") or "") == (response_payload.get("model_name") or "")
                    if same_provider and same_model:
                        turn["responses"][index] = response_payload
                        replaced = True
                        break
                if not replaced:
                    turn["responses"].append(response_payload)
                turn["responses"] = self._ordered_responses(turn["responses"])

            chat["updated_at"] = now
            self._save_locked()
            return copy.deepcopy(message_payload)

    def build_ollama_history(
        self,
        chat_id: str,
        model_name: str,
        *,
        max_messages: int | None = None,
        max_chars: int | None = None,
    ) -> list[dict]:
        """
        Build the selected model's local conversation context for Ollama.

        User messages are always included. Assistant messages are limited to the
        selected Ollama model so model-specific context stays coherent.
        """
        chat = self.get_chat(chat_id)
        if chat is None:
            return []

        history: list[dict] = []
        for message in chat["messages"]:
            if message["role"] == "user":
                attachments = _normalize_attachments(message.get("attachments") or [])
                history.append(
                    {
                        "role": "user",
                        "content": build_ollama_user_content(
                            str(message["content"]),
                            attachments,
                        ),
                    }
                )
                continue

            if (
                message["role"] == "assistant"
                and message["provider"] == "ollama"
                and (message["model_name"] or "") == model_name
            ):
                history.append({"role": "assistant", "content": message["content"]})

        if max_messages and max_messages > 0 and len(history) > max_messages:
            history = history[-max_messages:]

        if max_chars and max_chars > 0:
            total_chars = 0
            trimmed_history: list[dict] = []
            for item in reversed(history):
                item_content = str(item.get("content") or "")
                item_chars = len(item_content)
                if trimmed_history and total_chars + item_chars > max_chars:
                    break
                trimmed_history.append(item)
                total_chars += item_chars
            history = list(reversed(trimmed_history))

        while len(history) > 1 and history[0].get("role") == "assistant":
            history.pop(0)

        return history

    def delete_chat(self, chat_id: str) -> bool:
        with self._lock:
            original_count = len(self._state.get("chats", []))
            self._state["chats"] = [
                chat for chat in self._state.get("chats", [])
                if chat["id"] != chat_id
            ]
            deleted = len(self._state["chats"]) != original_count
            if deleted:
                self._save_locked()
            return deleted
