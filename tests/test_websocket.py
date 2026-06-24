"""
WebSocket integration test — Tests end-to-end chat via WebSocket protocol.
Requires a running server at OPENHER_TEST_WS_URI or PORT (default 8000) and pytest-asyncio.
Skipped gracefully if dependencies are missing or server not running.
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

try:
    import websockets  # noqa: F401
    _HAS_WS = True
except ImportError:
    _HAS_WS = False

try:
    import pytest_asyncio  # noqa: F401
    _HAS_ASYNC = True
except ImportError:
    _HAS_ASYNC = False

# Use first available persona (dynamic, not hardcoded)
_PERSONA_A = "vivian"
_PERSONA_B = "luna"
_WS_PORT = os.getenv("PORT", "8000")
WS_URI = os.getenv("OPENHER_TEST_WS_URI", f"ws://127.0.0.1:{_WS_PORT}/ws/chat")


def connect_local_ws(websockets_module, uri: str):
    """Connect to localhost without honoring external proxy env vars."""
    try:
        return websockets_module.connect(uri, proxy=None)
    except TypeError:
        return websockets_module.connect(uri)


@pytest.mark.asyncio
@pytest.mark.skipif(not _HAS_WS, reason="websockets not installed")
@pytest.mark.skipif(not _HAS_ASYNC, reason="pytest-asyncio not installed")
async def test_websocket():
    import websockets

    print("=" * 60)
    print("WebSocket E2E Test")
    print("=" * 60)

    uri = WS_URI

    try:
        ws_conn = connect_local_ws(websockets, uri)
        ws = await ws_conn.__aenter__()
    except (OSError, ConnectionRefusedError):
        pytest.skip(f"Server not running at {uri}")
        return

    try:
        # ── Test 1: Chat with first persona ──
        print(f"\n📤 Chat → {_PERSONA_A}")
        await ws.send(json.dumps({
            "type": "chat",
            "content": "Hey, what's up?",
            "persona_id": _PERSONA_A,
            "user_name": "Tester",
        }))

        full_response = ""
        chat_started = False
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=30)
            msg = json.loads(raw)

            if msg["type"] == "chat_start":
                print(f"  ✅ chat_start, session: {msg['session_id']}")
                chat_started = True
            elif msg["type"] == "chat_chunk":
                full_response += msg["content"]
            elif msg["type"] == "chat_end":
                if not full_response:
                    full_response = msg.get("reply", "")
                print(f"  💬 {_PERSONA_A}: {full_response}")
                break
            elif msg["type"] == "error":
                print(f"  ❌ Error: {msg['content']}")
                break

        assert chat_started, "Should have received chat_start"
        assert full_response, "Should have received response content"

        # ── Test 2: Switch persona ──
        print(f"\n📤 Switch → {_PERSONA_B}")
        await ws.send(json.dumps({
            "type": "switch_persona",
            "persona_id": _PERSONA_B,
            "user_name": "Tester",
        }))

        msg = {}
        for _ in range(10):
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
            if msg["type"] == "persona_switched":
                break
            if msg["type"] in {"chat_start", "chat_chunk", "chat_end", "silence"}:
                continue
            if msg["type"] == "error":
                raise AssertionError(msg.get("content", "unknown websocket error"))
        assert msg["type"] == "persona_switched"
        print(f"  ✅ Switched: {msg['persona']}, session: {msg['session_id']}")

        # ── Test 3: Chat with second persona ──
        print(f"\n📤 Chat → {_PERSONA_B}")
        await ws.send(json.dumps({
            "type": "chat",
            "content": "Hi there!",
            "persona_id": _PERSONA_B,
        }))

        full_response = ""
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=30)
            msg = json.loads(raw)
            if msg["type"] == "chat_start":
                pass
            elif msg["type"] == "chat_chunk":
                full_response += msg["content"]
            elif msg["type"] == "chat_end":
                if not full_response:
                    full_response = msg.get("reply", "")
                print(f"  💬 {_PERSONA_B}: {full_response}")
                break

        assert full_response, "Second persona should respond"

        # ── Test 4: Status check ──
        print("\n📤 Status check")
        await ws.send(json.dumps({"type": "status"}))
        raw = await asyncio.wait_for(ws.recv(), timeout=5)
        msg = json.loads(raw)
        print(f"  ✅ Status: {msg}")
    finally:
        await ws_conn.__aexit__(None, None, None)

    print(f"\n{'=' * 60}")
    print("🎉 WebSocket tests passed!")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(test_websocket())
