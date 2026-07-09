"""Request protocol helpers for EverMemOS-compatible APIs."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Mapping
import uuid


APP_ID = "openher"
PROJECT_ID = "openher"
STORE_PATHS = ("/memories", "/memory/add")
GET_PATHS = ("/memory/get", "/memories/get")


def normalize_search_method(retrieve_method: str) -> str:
    method = {"rrf": "keyword"}.get(retrieve_method, retrieve_method)
    if method not in {"keyword", "vector", "hybrid", "agentic"}:
        return "keyword"
    return method


def search_top_k(config: Mapping[str, Any]) -> int:
    return max(
        int(config["facts_max_items"]),
        int(config["episodes_max_items"]),
        int(config["profile_max_items"]),
    )


def build_health_search_body() -> dict[str, object]:
    return {
        "filters": {"user_id": "__healthcheck__"},
        "query": "__healthcheck__",
        "method": "keyword",
        "top_k": 1,
    }


def build_oss_health_search_body() -> dict[str, object]:
    return {
        "query": "__healthcheck__",
        "method": "keyword",
        "user_id": "__healthcheck__",
        "app_id": APP_ID,
        "project_id": PROJECT_ID,
        "top_k": 1,
    }


def build_cloud_search_body(
    query: str,
    user_id: str,
    method: str,
    top_k: int,
) -> dict[str, object]:
    return {
        "filters": {"user_id": user_id},
        "query": query,
        "method": method,
        "top_k": top_k,
    }


def build_oss_search_body(
    query: str,
    user_id: str,
    group_id: str,
    method: str,
    top_k: int,
) -> dict[str, object]:
    body: dict[str, object] = {
        "query": query,
        "method": method,
        "user_id": user_id,
        "app_id": APP_ID,
        "project_id": PROJECT_ID,
        "include_profile": True,
        "top_k": top_k,
    }
    if group_id:
        body["filters"] = {"session_id": group_id}
    return body


def build_legacy_search_body(
    query: str,
    user_id: str,
    group_id: str,
    retrieve_method: str,
) -> dict[str, object]:
    body: dict[str, object] = {
        "query": query,
        "retrieve_method": retrieve_method,
        "user_id": user_id,
    }
    if group_id:
        body["group_ids"] = [group_id]
    return body


def build_memory_batch_body(
    user_id: str,
    group_id: str,
    messages: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "user_id": user_id,
        "app_id": APP_ID,
        "project_id": PROJECT_ID,
        "session_id": group_id or user_id,
        "messages": messages,
    }


def build_memory_flush_body(user_id: str, group_id: str) -> dict[str, object]:
    return {
        "session_id": group_id or user_id,
        "app_id": APP_ID,
        "project_id": PROJECT_ID,
    }


def build_turn_messages(
    user_id: str,
    persona_id: str,
    persona_name: str,
    user_name: str,
    user_message: str,
    agent_reply: str,
    timestamp_ms: int,
) -> list[dict[str, object]]:
    return [
        {
            "content": user_message,
            "timestamp": timestamp_ms,
            "sender_id": user_id,
            "sender_name": user_name,
            "role": "user",
        },
        {
            "content": agent_reply,
            "timestamp": timestamp_ms + 1,
            "sender_id": persona_id,
            "sender_name": persona_name,
            "role": "assistant",
        },
    ]


def build_proactive_messages(
    persona_id: str,
    persona_name: str,
    reply: str,
    timestamp_ms: int,
) -> list[dict[str, object]]:
    return [
        {
            "content": reply,
            "timestamp": timestamp_ms,
            "sender_id": persona_id,
            "sender_name": persona_name,
            "role": "assistant",
        }
    ]


def build_session_flush_messages(
    persona_id: str,
    timestamp_ms: int,
) -> list[dict[str, object]]:
    return [
        {
            "content": "[session_end]",
            "timestamp": timestamp_ms,
            "sender_id": persona_id,
            "sender_name": "system",
            "role": "assistant",
        }
    ]


def build_legacy_memory_payload(
    user_id: str,
    group_id: str,
    message: Mapping[str, Any],
    flush: bool,
    message_id: str | None = None,
) -> dict[str, object]:
    timestamp_ms = int(message["timestamp"])
    created_at = datetime.fromtimestamp(
        timestamp_ms / 1000,
        tz=timezone(timedelta(hours=8)),
    ).strftime("%Y-%m-%dT%H:%M:%S+08:00")
    payload: dict[str, object] = {
        "content": message["content"],
        "create_time": created_at,
        "message_id": message_id or str(uuid.uuid4()),
        "user_id": user_id,
        "sender": message["sender_id"],
        "sender_name": message.get("sender_name"),
        "role": message["role"],
    }
    if group_id:
        payload["group_id"] = group_id
    if flush:
        payload["flush"] = True
    return payload


def build_v1_get_body(
    user_id: str,
    memory_type: str,
    page_size: int = 20,
) -> dict[str, object]:
    return {
        "user_id": user_id,
        "app_id": APP_ID,
        "project_id": PROJECT_ID,
        "memory_type": memory_type,
        "page_size": page_size,
        "sort_order": "desc",
    }


def build_compat_get_body(
    user_id: str,
    memory_type: str,
    page_size: int = 20,
) -> dict[str, object]:
    body = build_v1_get_body(user_id, memory_type, page_size)
    body["filters"] = {"user_id": user_id}
    return body


def load_memory_v1_type(memory_type: str) -> str | None:
    return {
        "profile": "profile",
        "episodic_memory": "episode",
    }.get(memory_type)


def load_memory_collection_key(memory_type: str) -> str:
    return "profiles" if memory_type == "profile" else "episodes"


def build_legacy_list_body(
    user_id: str,
    group_id: str,
    memory_type: str,
) -> dict[str, object]:
    body: dict[str, object] = {"memory_type": memory_type, "user_id": user_id}
    if group_id:
        body["group_ids"] = [group_id]
    return body
