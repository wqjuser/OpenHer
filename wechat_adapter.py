"""
微信 ↔ OpenHer 适配层

通过 WebSocket 连接 OpenHer（与桌面端完全一致的通道），
再以 OpenAI 兼容格式暴露给 wechat-to-anything 桥。

启动:
    .venv/bin/python wechat_adapter.py
使用:
    npx wechat-to-anything http://localhost:8001/v1
"""

import os
import uuid
import json
import hashlib
import asyncio
import base64
from pathlib import Path

import aiohttp
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

# ── 配置 ──
OPENHER_BASE = os.getenv("OPENHER_BASE", "http://localhost:8000")
OPENHER_WS = os.getenv("OPENHER_WS", OPENHER_BASE.replace("http", "ws", 1))
PERSONA_ID = os.getenv("OPENHER_PERSONA", "luna")
CLIENT_ID = os.getenv("OPENHER_CLIENT_ID", "wechat-user")
ADAPTER_HOST = os.getenv("ADAPTER_HOST", "0.0.0.0")
ADAPTER_PORT = int(os.getenv("ADAPTER_PORT", "8001"))
PUBLIC_BASE = os.getenv("PUBLIC_BASE", f"http://localhost:{ADAPTER_PORT}")
BRIDGE_API = os.getenv("BRIDGE_API", "http://localhost:9099")

# ── 状态 ──
AUDIO_DIR = Path("/tmp/openher_wechat_audio")
AUDIO_DIR.mkdir(exist_ok=True)

app = FastAPI(title="OpenHer WeChat Adapter")


def _build_content(reply_text: str, modality: str, segment: dict,
                   audio_path: str | None = None) -> str:
    """将一个 segment 构建成 bridge 可识别的消息内容"""
    parts = []

    # 语音
    if modality == "语音" and audio_path:
        parts.append(f"[audio:{audio_path}]")
        return "\n".join(parts)
    elif modality == "静默":
        return ""

    # 文字/表情
    if reply_text:
        parts.append(reply_text)

    # 照片
    image_path = segment.get("image_path")
    image_url = segment.get("image_url")
    if image_path and os.path.isfile(image_path):
        import shutil
        img_name = os.path.basename(image_path)
        shutil.copy2(image_path, AUDIO_DIR / img_name)
        parts.append(f"\n![photo]({PUBLIC_BASE}/audio/{img_name})")
        print(f"[adapter] 📷 image: {image_path} ({os.path.getsize(image_path)//1024}KB)")
    elif image_url:
        full_url = f"{OPENHER_BASE}{image_url}"
        parts.append(f"\n![photo]({full_url})")

    return "\n".join(parts) if parts else ""


async def _send_via_bridge(to: str, content: str):
    """通过 bridge 的 /api/send 主动推送消息"""
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


async def _chat_via_ws(text: str, persona_id: str, client_id: str,
                       wechat_user: str = "") -> dict:
    """
    通过 WebSocket 与 OpenHer 交互（和桌面端完全一致的通道）。

    实时处理分段消息：每收到一个 chat_end 就立即通过 /api/send 推送，
    利用服务端内置的 delay 控制节奏（和桌面端一样）。

    返回最后一个 segment 的数据（用于构建 OpenAI response）。
    """
    ws_url = f"{OPENHER_WS}/ws/chat"
    last_segment = {}
    segment_count = 0
    tts_audio_path = None

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(ws_url, timeout=120) as ws:
            # 发送消息（和桌面端格式一致）
            await ws.send_json({
                "type": "chat",
                "content": text,
                "persona_id": persona_id,
                "client_id": client_id,
                "user_name": client_id,
            })

            # 接收事件流
            while True:
                # 收到 chat_end 后，用短超时等后续事件（分段/tts_audio）
                timeout = 120 if not last_segment else 5
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=timeout)
                except (asyncio.TimeoutError, TimeoutError):
                    break  # 超时，没有更多事件

                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    event_type = data.get("type", "")

                    if event_type == "chat_end":
                        segment_count += 1
                        reply = data.get("reply", "")
                        modality = data.get("modality", "文字")
                        print(f"[adapter] ← [{modality}] seg#{segment_count}: {reply[:40]}")

                        # 前一个 segment 通过 /api/send 推送
                        if last_segment and wechat_user:
                            prev_content = _build_content(
                                last_segment.get("reply", ""),
                                last_segment.get("modality", "文字"),
                                last_segment,
                            )
                            if prev_content:
                                await _send_via_bridge(wechat_user, prev_content)

                        last_segment = data

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
                        last_segment = {"reply": "", "modality": "静默"}
                        break

                    elif event_type == "error":
                        last_segment = {"reply": f"⚠️ {data.get('content', '未知错误')}", "modality": "文字"}
                        break

                    # chat_start / chat_chunk → 继续循环

                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break

    last_segment["_tts_audio_path"] = tts_audio_path
    last_segment["_segment_count"] = segment_count
    return last_segment


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """OpenAI 兼容接口 — wechat-to-anything 调用入口"""
    data = await request.json()
    messages = data.get("messages", [])
    wechat_user = data.get("user", "")  # 微信用户 ID（0.6.5+）
    if not messages:
        return _openai_response("(empty)")

    last_msg = messages[-1]

    # ── 1. 提取用户文本（兼容纯文本和 Vision 多模态格式）──
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

    # ── 2. 通过 WebSocket 调用 OpenHer ──
    # 内部实时发送分段（前 N-1 段通过 /api/send 推送，间隔由服务端控制）
    # 返回最后一段用于构建 response
    try:
        result = await _chat_via_ws(
            user_text.strip(), PERSONA_ID, effective_client_id,
            wechat_user=wechat_user,
        )
    except Exception as e:
        print(f"[adapter] ✗ WebSocket 异常: {e}")
        return _openai_response(f"⚠️ 连接失败")

    # ── 3. 构建最后一段回复 ──
    reply_text = result.get("reply", "")
    modality = result.get("modality", "文字")
    audio_path = result.get("audio_path") or result.get("_tts_audio_path")
    seg_count = result.get("_segment_count", 1)

    if seg_count > 1:
        print(f"[adapter] ✂️ {seg_count} segments delivered")

    content = _build_content(reply_text, modality, result, audio_path=audio_path)
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
    return {"status": "ok", "persona": PERSONA_ID, "openher": OPENHER_BASE}


# ── 内部工具 ──

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




if __name__ == "__main__":
    print(f"🔗 OpenHer WeChat Adapter (WebSocket)")
    print(f"   OpenHer: {OPENHER_BASE}")
    print(f"   WS:      {OPENHER_WS}/ws/chat")
    print(f"   Bridge:  {BRIDGE_API}/api/send")
    print(f"   Persona: {PERSONA_ID}")
    print(f"   Client:  {CLIENT_ID}")
    print(f"   Listen:  {ADAPTER_HOST}:{ADAPTER_PORT}")
    print()
    print(f"   npx wechat-to-anything http://localhost:{ADAPTER_PORT}/v1")
    print()
    uvicorn.run(app, host=ADAPTER_HOST, port=ADAPTER_PORT)
