"""
微信 ↔ OpenHer 适配层（持久 WebSocket 版）

与桌面端完全一致的连接模式：
  - 启动时建立一个持久 WebSocket 到 OpenHer /ws/chat
  - 所有聊天消息通过此连接收发
  - 自驱消息（proactive）通过同一连接接收并推送到微信
  - 断线自动重连

启动:
    .venv/bin/python wechat_adapter.py
使用:
    npx wechat-to-anything http://localhost:8001/v1
"""

import asyncio
import base64
import hashlib
import json
import os
import uuid
import time
from pathlib import Path
from collections import defaultdict

import aiohttp
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

# ── 配置 ──
OPENHER_BASE = os.getenv("OPENHER_BASE", "http://localhost:8000")
OPENHER_WS = OPENHER_BASE.replace("http://", "ws://").replace("https://", "wss://")
PERSONA_ID = os.getenv("PERSONA_ID", "luna")
CLIENT_ID = os.getenv("CLIENT_ID", "wechat-user")
ADAPTER_PORT = int(os.getenv("ADAPTER_PORT", "8001"))
PUBLIC_BASE = os.getenv("PUBLIC_BASE", f"http://localhost:{ADAPTER_PORT}")
BRIDGE_API = os.getenv("BRIDGE_API", "http://localhost:9099")

# ── 状态 ──
AUDIO_DIR = Path("/tmp/openher_wechat_audio")
AUDIO_DIR.mkdir(exist_ok=True)

app = FastAPI(title="OpenHer WeChat Adapter")


# ══════════════════════════════════════════════════════════════
# 持久 WebSocket 连接管理
# ══════════════════════════════════════════════════════════════

class PersistentWS:
    """
    管理一个持久 WebSocket 连接到 OpenHer /ws/chat。

    - 启动时连接，断线自动重连
    - chat 请求通过 send_and_wait() 发消息、等回复
    - 后台监听 proactive 事件并转发微信
    """

    def __init__(self):
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._session: aiohttp.ClientSession | None = None
        self._listen_task: asyncio.Task | None = None
        self._connected = asyncio.Event()
        self._session_id: str | None = None

        # 聊天请求的回复通道：一次只处理一个聊天（串行）
        self._chat_lock = asyncio.Lock()
        self._chat_response: asyncio.Queue[dict] | None = None
        self._chat_wechat_user: str = ""

        # 记录每个微信用户最后使用的 client_id
        self._wechat_users: set[str] = set()

    async def start(self):
        """启动持久连接（在 FastAPI lifespan 中调用）"""
        self._session = aiohttp.ClientSession()
        self._listen_task = asyncio.create_task(self._connect_loop())

    async def stop(self):
        """关闭连接"""
        if self._listen_task:
            self._listen_task.cancel()
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._session:
            await self._session.close()

    async def _connect_loop(self):
        """持续保持连接，断线重连"""
        while True:
            try:
                ws_url = f"{OPENHER_WS}/ws/chat"
                print(f"[ws] 连接 {ws_url} ...")
                if self._session is None:
                    raise RuntimeError("WebSocket session is not initialized")
                self._ws = await self._session.ws_connect(
                    ws_url,
                    receive_timeout=120.0,
                    heartbeat=30,
                )
                self._connected.set()
                print(f"[ws] ✅ 已连接")

                await self._listen()

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[ws] ✗ 连接失败: {e}")

            self._connected.clear()
            print(f"[ws] 3 秒后重连...")
            await asyncio.sleep(3)

    async def _listen(self):
        """监听所有 WebSocket 事件"""
        if self._ws is None:
            return
        async for msg in self._ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                event_type = data.get("type", "")

                if event_type == "proactive":
                    # 自驱消息 → 转发微信
                    await self._handle_proactive(data)

                elif self._chat_response is not None:
                    # 聊天回复 → 发到等待队列
                    await self._chat_response.put(data)

                else:
                    # 没有人在等回复，可能是心跳或其他事件
                    if event_type not in ("pong", ""):
                        print(f"[ws] 未处理事件: {event_type}")

            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                print(f"[ws] 连接关闭: {msg.type}")
                break

    async def _handle_proactive(self, data: dict):
        """处理自驱消息：转发到微信"""
        content = data.get("content", "")
        modality = data.get("modality", "文字")
        drive = data.get("drive", "")
        persona = data.get("persona", "")

        if not content:
            return

        print(f"[proactive] 💭 {persona} ({drive}): {content[:50]}")

        # 构建消息内容
        msg_content = _build_content(content, modality, data)
        if not msg_content:
            return

        # 发送给所有已知的微信用户
        for wechat_user in self._wechat_users:
            await _send_via_bridge(wechat_user, msg_content)

    async def send_and_wait(self, text: str, persona_id: str, client_id: str,
                            wechat_user: str = "") -> list[dict]:
        """
        发送聊天消息并等待所有回复 segments。

        返回所有 chat_end 事件的列表。
        """
        async with self._chat_lock:
            # 等待连接就绪
            await asyncio.wait_for(self._connected.wait(), timeout=10)

            if wechat_user:
                self._wechat_users.add(wechat_user)

            self._chat_response = asyncio.Queue()
            self._chat_wechat_user = wechat_user
            segments: list[dict] = []
            tts_audio_path = None

            try:
                # 发送消息
                if self._ws is None:
                    raise RuntimeError("WebSocket is not connected")
                await self._ws.send_json({
                    "type": "chat",
                    "content": text,
                    "persona_id": persona_id,
                    "client_id": client_id,
                    "user_name": client_id,
                })

                # 接收回复事件流
                while True:
                    timeout = 120 if not segments else 5
                    try:
                        data = await asyncio.wait_for(
                            self._chat_response.get(), timeout=timeout
                        )
                    except (asyncio.TimeoutError, TimeoutError):
                        break

                    event_type = data.get("type", "")

                    if event_type == "chat_end":
                        reply = data.get("reply", "")
                        modality = data.get("modality", "文字")
                        print(f"[adapter] ← [{modality}] seg#{len(segments)+1}: {reply[:40]}")

                        # 前一个 segment 通过 /api/send 推送
                        if segments and wechat_user:
                            prev = segments[-1]
                            prev_content = _build_content(
                                prev.get("reply", ""),
                                prev.get("modality", "文字"),
                                prev,
                            )
                            if prev_content:
                                await _send_via_bridge(wechat_user, prev_content)

                        segments.append(data)

                    elif event_type == "tts_audio":
                        audio_b64 = data.get("audio", "")
                        if audio_b64:
                            audio_bytes = base64.b64decode(audio_b64)
                            audio_hash = hashlib.md5(audio_bytes).hexdigest()[:16]
                            audio_file = AUDIO_DIR / f"{audio_hash}.wav"
                            audio_file.write_bytes(audio_bytes)
                            tts_audio_path = str(audio_file)
                            print(f"[adapter] 🔊 TTS: {audio_file} ({len(audio_bytes)//1024}KB)")
                        break

                    elif event_type == "silence":
                        segments.append({"reply": "", "modality": "静默"})
                        break

                    elif event_type == "error":
                        segments.append({
                            "reply": f"⚠️ {data.get('content', '未知错误')}",
                            "modality": "文字",
                        })
                        break

                    # chat_start / chat_chunk → 继续

            finally:
                self._chat_response = None

            # 附加 TTS 路径到最后一个 segment
            if segments:
                segments[-1]["_tts_audio_path"] = tts_audio_path
                segments[-1]["_segment_count"] = len(segments)

            return segments


# 全局持久连接
_persistent_ws = PersistentWS()


# ══════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════

def _build_content(reply_text: str, modality: str, segment: dict,
                   audio_path: str | None = None) -> str:
    """将一个 segment 构建成 bridge 可识别的消息内容"""
    if modality == "静默" or not reply_text.strip():
        return ""

    # 语音：优先用 TTS 音频
    effective_audio = audio_path or segment.get("_tts_audio_path")
    if effective_audio:
        return f"[audio:{effective_audio}]"

    # 图片
    image_url = segment.get("image_url", "")
    if image_url and modality in ("自拍", "照片", "图片"):
        if image_url.startswith("/"):
            image_url = f"{PUBLIC_BASE}{image_url}"
        return f"![photo]({image_url})"

    # 文字 / 表情
    return reply_text


async def _send_via_bridge(to: str, content: str):
    """通过 bridge /api/send 发送消息到微信"""
    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(
                f"{BRIDGE_API}/api/send",
                json={"to": to, "content": content},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    print(f"[adapter] 📤 sent: {content[:50]}")
                else:
                    err = await resp.text()
                    print(f"[adapter] ✗ /api/send failed: {resp.status} {err[:100]}")
    except Exception as e:
        print(f"[adapter] ✗ /api/send error: {e}")


def _openai_response(content: str) -> dict:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop",
        }],
    }


# ══════════════════════════════════════════════════════════════
# HTTP 端点（OpenAI 兼容 — bridge 调用入口）
# ══════════════════════════════════════════════════════════════

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """OpenAI 兼容接口 — wechat-to-anything 调用入口"""
    data = await request.json()
    messages = data.get("messages", [])
    wechat_user = data.get("user", "")
    if not messages:
        return _openai_response("(empty)")

    last_msg = messages[-1]

    # 提取用户文本
    user_text = ""
    user_images = []

    if isinstance(last_msg.get("content"), str):
        user_text = last_msg["content"]
    elif isinstance(last_msg.get("content"), list):
        for part in last_msg["content"]:
            if part.get("type") == "text":
                user_text += part.get("text", "")
            elif part.get("type") == "image_url":
                user_images.append(part["image_url"]["url"])

    if user_images:
        user_text += f"\n[用户发送了{len(user_images)}张图片]"

    if not user_text.strip():
        return _openai_response("(empty)")

    effective_client_id = wechat_user or CLIENT_ID
    print(f"[adapter] → {user_text.strip()[:60]}")

    # 通过持久 WebSocket 发送并等待回复
    try:
        segments = await _persistent_ws.send_and_wait(
            user_text.strip(), PERSONA_ID, effective_client_id,
            wechat_user=wechat_user,
        )
    except Exception as e:
        print(f"[adapter] ✗ WebSocket 异常: {e}")
        return _openai_response("⚠️ 连接失败")

    if not segments:
        return _openai_response("...")

    # 最后一段作为 response 返回给 bridge
    last = segments[-1]
    reply_text = last.get("reply", "")
    modality = last.get("modality", "文字")
    audio_path = last.get("audio_path") or last.get("_tts_audio_path")
    seg_count = last.get("_segment_count", 1)

    if seg_count > 1:
        print(f"[adapter] ✂️ {seg_count} segments delivered")

    content = _build_content(reply_text, modality, last, audio_path=audio_path)
    return _openai_response(content if content else "...")


@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    """提供音频/图片文件下载"""
    filepath = AUDIO_DIR / filename
    if not filepath.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(str(filepath), media_type="audio/mpeg", filename=filename)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "persona": PERSONA_ID,
        "openher": OPENHER_BASE,
        "ws_connected": _persistent_ws._connected.is_set(),
        "wechat_users": list(_persistent_ws._wechat_users),
    }


# ══════════════════════════════════════════════════════════════
# Lifespan — 启动 / 关闭持久连接
# ══════════════════════════════════════════════════════════════

@app.on_event("startup")
async def on_startup():
    await _persistent_ws.start()


@app.on_event("shutdown")
async def on_shutdown():
    await _persistent_ws.stop()


# ══════════════════════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"🔗 OpenHer WeChat Adapter (持久 WebSocket)")
    print(f"   OpenHer: {OPENHER_BASE}")
    print(f"   WS:      {OPENHER_WS}/ws/chat")
    print(f"   Bridge:  {BRIDGE_API}/api/send")
    print(f"   Persona: {PERSONA_ID}")
    print(f"   Client:  {CLIENT_ID}")
    print(f"   Listen:  0.0.0.0:{ADAPTER_PORT}")
    print()
    print(f"   npx wechat-to-anything http://localhost:{ADAPTER_PORT}/v1")
    print()
    uvicorn.run(app, host="0.0.0.0", port=ADAPTER_PORT, log_level="info")
