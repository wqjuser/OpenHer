from __future__ import annotations


def test_search_protocol_builds_cloud_oss_and_legacy_payloads():
    from providers.memory.evermemos import protocol

    assert protocol.normalize_search_method("rrf") == "keyword"
    assert protocol.normalize_search_method("hybrid") == "hybrid"
    assert protocol.normalize_search_method("unsupported") == "keyword"
    assert protocol.search_top_k({"facts_max_items": 2, "episodes_max_items": 5, "profile_max_items": 3}) == 5

    assert protocol.build_health_search_body() == {
        "filters": {"user_id": "__healthcheck__"},
        "query": "__healthcheck__",
        "method": "keyword",
        "top_k": 1,
    }
    assert protocol.build_cloud_search_body(
        query="where did we test memories?",
        user_id="u",
        method="keyword",
        top_k=5,
    ) == {
        "filters": {"user_id": "u"},
        "query": "where did we test memories?",
        "method": "keyword",
        "top_k": 5,
    }
    assert protocol.build_oss_search_body(
        query="where did we test memories?",
        user_id="u",
        group_id="g",
        method="keyword",
        top_k=5,
    ) == {
        "query": "where did we test memories?",
        "method": "keyword",
        "user_id": "u",
        "app_id": "openher",
        "project_id": "openher",
        "include_profile": True,
        "top_k": 5,
        "filters": {"session_id": "g"},
    }
    assert protocol.build_legacy_search_body(
        query="where did we test memories?",
        user_id="u",
        group_id="g",
        retrieve_method="rrf",
    ) == {
        "query": "where did we test memories?",
        "retrieve_method": "rrf",
        "user_id": "u",
        "group_ids": ["g"],
    }


def test_store_protocol_builds_batch_and_legacy_payloads():
    from providers.memory.evermemos import protocol

    message = {
        "content": "hello",
        "timestamp": 1_720_000_000_000,
        "sender_id": "u",
        "sender_name": "QA",
        "role": "user",
    }

    assert protocol.build_memory_batch_body("u", "g", [message]) == {
        "user_id": "u",
        "app_id": "openher",
        "project_id": "openher",
        "session_id": "g",
        "messages": [message],
    }
    assert protocol.build_memory_batch_body("u", "", [message])["session_id"] == "u"

    assert protocol.build_legacy_memory_payload(
        user_id="u",
        group_id="g",
        message=message,
        flush=True,
        message_id="message-1",
    ) == {
        "content": "hello",
        "create_time": "2024-07-03T17:46:40+08:00",
        "message_id": "message-1",
        "user_id": "u",
        "sender": "u",
        "sender_name": "QA",
        "role": "user",
        "group_id": "g",
        "flush": True,
    }


def test_get_protocol_builds_v1_and_compat_payloads():
    from providers.memory.evermemos import protocol

    assert protocol.GET_PATHS == ("/memory/get", "/memories/get")
    assert protocol.STORE_PATHS == ("/memories", "/memory/add")

    assert protocol.build_v1_get_body("u", "profile") == {
        "user_id": "u",
        "app_id": "openher",
        "project_id": "openher",
        "memory_type": "profile",
        "page_size": 20,
        "sort_order": "desc",
    }
    assert protocol.build_compat_get_body("u", "episodic_memory") == {
        "user_id": "u",
        "app_id": "openher",
        "project_id": "openher",
        "memory_type": "episodic_memory",
        "page_size": 20,
        "sort_order": "desc",
        "filters": {"user_id": "u"},
    }


def test_protocol_builds_health_flush_and_message_payloads():
    from providers.memory.evermemos import protocol

    assert protocol.build_oss_health_search_body() == {
        "query": "__healthcheck__",
        "method": "keyword",
        "user_id": "__healthcheck__",
        "app_id": "openher",
        "project_id": "openher",
        "top_k": 1,
    }
    assert protocol.build_memory_flush_body("u", "g") == {
        "session_id": "g",
        "app_id": "openher",
        "project_id": "openher",
    }
    assert protocol.build_memory_flush_body("u", "")["session_id"] == "u"

    assert protocol.build_turn_messages(
        user_id="u",
        persona_id="luna",
        persona_name="Luna",
        user_name="QA",
        user_message="hi",
        agent_reply="hello",
        timestamp_ms=1000,
    ) == [
        {
            "content": "hi",
            "timestamp": 1000,
            "sender_id": "u",
            "sender_name": "QA",
            "role": "user",
        },
        {
            "content": "hello",
            "timestamp": 1001,
            "sender_id": "luna",
            "sender_name": "Luna",
            "role": "assistant",
        },
    ]
    assert protocol.build_proactive_messages(
        persona_id="luna",
        persona_name="Luna",
        reply="ping",
        timestamp_ms=2000,
    ) == [
        {
            "content": "ping",
            "timestamp": 2000,
            "sender_id": "luna",
            "sender_name": "Luna",
            "role": "assistant",
        }
    ]
    assert protocol.build_session_flush_messages("luna", 3000) == [
        {
            "content": "[session_end]",
            "timestamp": 3000,
            "sender_id": "luna",
            "sender_name": "system",
            "role": "assistant",
        }
    ]
