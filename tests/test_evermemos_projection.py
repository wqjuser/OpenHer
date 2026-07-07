from __future__ import annotations

import pytest


CFG = {
    "facts_max_items": 2,
    "profile_max_items": 2,
    "episodes_max_items": 2,
    "foresight_max_items": 1,
    "foresight_max_chars": 10,
}


def test_projection_builds_empty_session_context():
    from providers.memory.evermemos import projection

    ctx = projection.empty_session_context()

    assert ctx.user_profile == ""
    assert ctx.episode_summary == ""
    assert ctx.foresight_text == ""
    assert ctx.interaction_count == 0
    assert ctx.has_history is False
    assert ctx.relationship_depth == 0.0
    assert ctx.pending_foresight == 0.0


def test_projection_builds_session_context_from_mixed_memories():
    from providers.memory.evermemos import projection

    memories = [
        {"profile_data": {"favorite": "tea", "user_name": "skip", "tone": "warm"}, "memcell_count": 4},
        {"atomic_fact": "likes rain"},
        {"atomic_fact": "writes tests"},
        {"summary": "first episode"},
        {"episode_id": "episode-2", "narrative": "second episode"},
        {"foresight": "bring umbrella soon"},
    ]

    ctx = projection.build_session_context_from_memories(memories, CFG)

    assert ctx.user_profile == "【用户画像】favorite: tea；tone: warm\n【已知偏好/事实】likes rain；writes tests"
    assert ctx.episode_summary == "first episode；second episode"
    assert ctx.foresight_text == "bring umbr"
    assert ctx.interaction_count == 4
    assert ctx.has_history is True
    assert ctx.relationship_depth == 0.487
    assert ctx.pending_foresight == 0.487
    assert ctx._fact_count == 2
    assert ctx._profile_count == 2
    assert ctx._episode_count == 2
    assert ctx._foresight_count == 1


def test_projection_flattens_load_results_and_search_response_memories():
    from providers.memory.evermemos import projection

    assert projection.flatten_memory_results([
        {"result": {"memories": [{"atomic_fact": "fact one"}]}},
        None,
        {"result": {"memories": "not-a-list"}},
        {"result": {"memories": [{"summary": "episode one"}]}},
    ]) == [{"atomic_fact": "fact one"}, {"summary": "episode one"}]

    memories = projection.extract_search_memories(
        {
            "data": {
                "episodes": [
                    {
                        "episode_id": "episode-1",
                        "summary": "rain walk",
                        "atomic_facts": [
                            {"content": "likes rain"},
                            {"fact": "carries umbrella"},
                        ],
                    }
                ],
                "profiles": [{"profile_data": {"city": "Shanghai"}}],
            }
        }
    )

    assert memories == [
        {
            "episode_id": "episode-1",
            "summary": "rain walk",
            "atomic_facts": [
                {"content": "likes rain"},
                {"fact": "carries umbrella"},
            ],
        },
        {"profile_data": {"city": "Shanghai"}},
        {"atomic_fact": "likes rain"},
        {"atomic_fact": "carries umbrella"},
    ]


def test_projection_builds_relevant_memory_tuple_and_relationship_vector():
    from providers.memory.evermemos import projection
    from providers.memory.evermemos.types import SessionContext

    projection_result = projection.build_relevant_memory_projection(
        [
            {"atomic_fact": "likes rain"},
            {"atomic_fact": "writes tests"},
            {"atomic_fact": "ignored by limit"},
            {"summary": "rain walk"},
            {"episode_id": "episode-2", "content": "debug session"},
            {"profile_data": {"city": "Shanghai", "tone": "warm", "user_id": "skip"}},
        ],
        CFG,
    )

    assert projection_result.as_tuple() == (
        "likes rain；writes tests",
        "rain walk；debug session",
        "city: Shanghai；tone: warm",
    )
    assert len(projection_result.facts) == 2
    assert len(projection_result.episodes) == 2
    assert len(projection_result.profile_attrs) == 2

    vector = projection.relationship_vector_from_context(
        SessionContext(
            user_profile="",
            episode_summary="",
            foresight_text="",
            interaction_count=40,
            has_history=True,
            relationship_depth=0.25,
            pending_foresight=0.6,
        )
    )

    assert vector == {
        "relationship_depth": 0.25,
        "emotional_valence": 0.0,
        "trust_level": pytest.approx(0.632, abs=0.001),
        "pending_foresight": 0.6,
    }
