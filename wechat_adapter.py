"""
微信 ↔ OpenHer 适配层

把 wechat-to-anything 的 OpenAI 兼容协议翻译为 OpenHer REST API。
独立进程，不修改 OpenHer 或 wechat-to-anything 任何代码。

启动:
    .venv/bin/python wechat_adapter.py
使用:
    npx wechat-to-anything http://localhost:8001/v1
"""

import os
import uuid
import json
import hashlib
from pathlib import Path

import aiohttp
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse

# ── 配置 ──
OPENHER_BASE = os.getenv("OPENHER_BASE", "http://localhost:8000")
PERSONA_ID = os.getenv("OPENHER_PERSONA", "luna")
CLIENT_ID = os.getenv("OPENHER_CLIENT_ID", "wechat-user")  # 固定值，保持跨重启的记忆连续性
ADAPTER_HOST = os.getenv("ADAPTER_HOST", "0.0.0.0")
ADAPTER_PORT = int(os.getenv("ADAPTER_PORT", "8001"))
PUBLIC_BASE = os.getenv("PUBLIC_BASE", f"http://localhost:{ADAPTER_PORT}")

# ── 状态 ──
session_id = None  # 单会话复用
AUDIO_DIR = Path("/tmp/openher_wechat_audio")
AUDIO_DIR.mkdir(exist_ok=True)

app = FastAPI(title="OpenHer WeChat Adapter")


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """OpenAI 兼容接口 — wechat-to-anything 调用入口"""
    global session_id

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

    # ── 2. 调用 OpenHer /api/chat ──
    # 用微信用户 ID 作为 client_id，确保每个用户独立记忆
    effective_client_id = wechat_user or CLIENT_ID
    payload = {
        "message": user_text.strip(),
        "persona_id": PERSONA_ID,
        "client_id": effective_client_id,
        "user_name": effective_client_id,
    }
    if session_id:
        payload["session_id"] = session_id

    print(f"[adapter] → {user_text.strip()[:60]}")

    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(
                f"{OPENHER_BASE}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    print(f"[adapter] ✗ {resp.status}: {err[:200]}")
                    return _openai_response(f"⚠️ 服务异常({resp.status})")
                result = await resp.json()
    except Exception as e:
        print(f"[adapter] ✗ 请求异常: {e}")
        return _openai_response(f"⚠️ 连接失败")

    # 保存 session_id 以复用
    session_id = result.get("session_id", session_id)

    reply_text = result.get("response", "")
    modality = result.get("modality", "文字")
    image_url = result.get("image_url")
    audio_path = result.get("audio_path")  # 人格引擎生成的 TTS（带情感+声线）

    print(f"[adapter] ← [{modality}] {reply_text[:60]}")
    if audio_path:
        print(f"[adapter] 🔊 engine audio: {audio_path}")

    # ── 3. 构建回复 ──
    parts = []

    # 语音模态：优先用人格引擎的音频，不重复发文字
    if modality == "语音" and audio_path:
        parts.append(f"[audio:{audio_path}]")
    elif modality == "语音" and reply_text:
        # fallback: 引擎没生成音频，用 /api/tts
        audio_url = await _generate_tts(reply_text)
        if audio_url:
            parts.append(f"[audio:{audio_url}]")
        else:
            parts.append(reply_text)
    else:
        # 文字/照片模态
        if reply_text:
            parts.append(reply_text)

    # 照片：复制到 adapter 目录，bridge 0.5.4 下载→CDN→发送
    image_path = result.get("image_path")
    if image_path and os.path.isfile(image_path):
        import shutil
        img_name = os.path.basename(image_path)
        shutil.copy2(image_path, AUDIO_DIR / img_name)
        parts.append(f"\n![photo]({PUBLIC_BASE}/audio/{img_name})")
        print(f"[adapter] 📷 image: {image_path} ({os.path.getsize(image_path)//1024}KB)")
    elif image_url:
        full_image_url = f"{OPENHER_BASE}{image_url}"
        parts.append(f"\n![photo]({full_image_url})")

    content = "\n".join(parts) if parts else "..."
    return _openai_response(content)


@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    """提供 TTS 音频文件下载"""
    filepath = AUDIO_DIR / filename
    if not filepath.is_file():
        return {"error": "not found"}, 404
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


async def _generate_tts(text: str):
    """调用 OpenHer /api/tts，保存音频，返回 HTTP URL（bridge 下载→转码→CDN→发送）"""
    try:
        text_hash = hashlib.md5(text.encode()).hexdigest()[:12]
        filename = f"{text_hash}.mp3"
        filepath = AUDIO_DIR / filename

        if not filepath.exists():
            async with aiohttp.ClientSession() as http:
                async with http.get(
                    f"{OPENHER_BASE}/api/tts",
                    params={"text": text, "voice": "Cherry"},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        filepath.write_bytes(await resp.read())
                        print(f"[adapter] 🔊 TTS saved: {filepath}")
                    else:
                        print(f"[adapter] TTS 失败: {resp.status}")
                        return None

        return str(filepath)  # 本地路径，bridge 直接 ffmpeg 处理

    except Exception as e:
        print(f"[adapter] TTS 错误: {e}")
        return None


if __name__ == "__main__":
    print(f"🔗 OpenHer WeChat Adapter")
    print(f"   OpenHer: {OPENHER_BASE}")
    print(f"   Persona: {PERSONA_ID}")
    print(f"   Client:  {CLIENT_ID}")
    print(f"   Listen:  {ADAPTER_HOST}:{ADAPTER_PORT}")
    print()
    print(f"   npx wechat-to-anything http://localhost:{ADAPTER_PORT}/v1")
    print()
    uvicorn.run(app, host=ADAPTER_HOST, port=ADAPTER_PORT)
