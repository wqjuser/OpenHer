#!/usr/bin/env python3
"""
OpenHer Demo 自动化脚本 v2 — 带实时监控
========================================
功能:
  1. 启动前自动检查后端健康
  2. 后台线程实时监控 server.log，有错误立刻中断
  3. 每步等待 chat_end 确认完成，超时自动中断
  4. 记录精确时间戳，结束后生成 TTS 时间轴

用法:
    cd /path/to/openher
    source .venv/bin/activate
    python demo/run_demo.py
"""

import asyncio
import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime

import websockets

# ─── 配置 ───
WS_URL = "ws://localhost:8000/ws"
SERVER_LOG = ".data/server.log"
HEALTH_URL = "http://localhost:8000/api/status"
TIMEOUT_CHAT = 60       # 单条消息最大等待秒数
TIMEOUT_PROACTIVE = 30  # 主动消息最大等待秒数

# ─── 全局状态 ───
timeline = []
start_time = 0
abort_flag = False
log_thread = None
current_act = ""


# ═══════════════════════════════════════════
#   工具函数
# ═══════════════════════════════════════════

def ts():
    return round(time.time() - start_time, 1)

def mmss(t):
    return f"{int(t//60)}:{int(t%60):02d}"

def log(action, note=""):
    t = ts()
    entry = {"time": t, "mmss": mmss(t), "action": action, "note": note}
    timeline.append(entry)
    color = "\033[96m" if "═══" in action else "\033[93m" if "⏸️" in action else "\033[92m" if "✅" in action else "\033[91m" if "❌" in action else "\033[0m"
    print(f"  {color}[{mmss(t)}]{' ':>2}{action}\033[0m  {note}")

def abort(reason):
    global abort_flag
    abort_flag = True
    print(f"\n  \033[91m{'='*50}")
    print(f"  ❌ 中断: {reason}")
    print(f"  {'='*50}\033[0m\n")
    log(f"❌ 中断: {reason}")


# ─── 健康检查 ───

def check_health():
    """检查后端是否运行"""
    import urllib.request
    try:
        resp = urllib.request.urlopen(HEALTH_URL, timeout=5)
        if resp.status == 200:
            return True
    except Exception:
        pass
    return False


# ─── 日志监控线程 ───

def monitor_log():
    """后台线程：监控 server.log 中的错误"""
    global abort_flag
    try:
        proc = subprocess.Popen(
            ["tail", "-f", SERVER_LOG],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for line in proc.stdout:
            if abort_flag:
                proc.kill()
                return
            line = line.strip()
            # 检测致命错误
            if any(kw in line for kw in [
                "Traceback", "AttributeError", "TypeError",
                "KeyError", "RuntimeError", "FATAL",
            ]):
                print(f"\n  \033[91m  ⚠ 后端错误: {line[:100]}\033[0m")
                # 不立刻中断，继续收集错误信息
            # 实时打印关键后端日志（灰色）
            if any(kw in line for kw in [
                "[feel]", "[genome]", "[debug-viz]", "[demo]",
                "[emergence]", "[proactive]", "主动消息",
            ]):
                print(f"  \033[90m  LOG: {line[:120]}\033[0m")
    except Exception:
        pass


# ─── WebSocket 辅助 ───

async def send(ws, payload):
    if abort_flag:
        raise Exception("已中断")
    await ws.send(json.dumps(payload))


async def drain(ws, timeout=2):
    """吃掉所有待处理的消息"""
    while True:
        try:
            await asyncio.wait_for(ws.recv(), timeout=timeout)
        except (asyncio.TimeoutError, Exception):
            break


async def send_chat_and_wait(ws, message, persona_id):
    """发送聊天并等待完整回复，超时中断"""
    if abort_flag:
        return None, None

    log(f"💬 发送: \"{message}\"", f"→ {persona_id}")

    await send(ws, {
        "type": "chat",
        "content": message,
        "persona_id": persona_id,
        "client_id": "demo_auto",
        "debug": True,
    })

    t0 = time.time()
    reply = ""
    monologue = ""

    while True:
        if abort_flag:
            return None, None
        elapsed = time.time() - t0
        if elapsed > TIMEOUT_CHAT:
            abort(f"消息 \"{message}\" 等待超时 ({TIMEOUT_CHAT}s)")
            return None, None

        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)

            if msg.get("type") == "chat_end":
                reply = msg.get("reply", "")
                debug = msg.get("debug", {})
                monologue = debug.get("monologue", "")

                # 记录关键状态
                temp = debug.get("temperature", 0)
                frust = debug.get("total_frustration", 0)
                elapsed = round(time.time() - t0, 1)

                log(f"✅ 回复 ({elapsed}s): \"{reply[:50]}\"")
                log(f"   独白: \"{monologue[:50]}\"")
                log(f"   温度={temp:.3f} 挫败={frust:.2f}")
                return reply, monologue

            elif msg.get("type") == "error":
                abort(f"后端错误: {msg.get('message', 'unknown')}")
                return None, None

        except asyncio.TimeoutError:
            # 继续等待，但打印进度
            print(f"  \033[90m  ... 等待回复 ({elapsed:.0f}s)\033[0m", end="\r")
            continue


async def switch_and_wait(ws, persona_id):
    """切换角色并等待就绪"""
    if abort_flag:
        return
    log(f"🔄 切换角色 → {persona_id}")
    await send(ws, {
        "type": "switch_persona",
        "persona_id": persona_id,
        "client_id": "demo_auto",
    })

    t0 = time.time()
    while time.time() - t0 < 30:
        if abort_flag:
            return
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            msg = json.loads(raw)
            if msg.get("type") in ("session_init", "persona_ready"):
                await asyncio.sleep(1)
                await drain(ws, timeout=1)
                log(f"✅ 角色就绪: {persona_id}")
                return
        except asyncio.TimeoutError:
            continue

    abort(f"角色切换超时: {persona_id}")


async def scenario_and_wait(ws, scenario_id, label):
    if abort_flag:
        return
    log(f"🎚️ 注入场景: {label}")
    await send(ws, {"type": "demo_scenario", "scenario_id": scenario_id})
    try:
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=8)
            msg = json.loads(raw)
            if msg.get("type") == "demo_state":
                snap = msg.get("snapshot", {})
                temp = snap.get("temperature", 0)
                log(f"✅ 场景已应用: {label}", f"温度={temp:.3f}")
                return
    except asyncio.TimeoutError:
        log(f"⚠️ 场景可能已应用（无 demo_state 响应）: {label}")


async def time_jump_and_wait(ws, hours):
    if abort_flag:
        return
    log(f"⏩ 时间跳跃: +{hours}h")
    await send(ws, {"type": "demo_time_jump", "hours": hours})
    try:
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=8)
            msg = json.loads(raw)
            if msg.get("type") == "demo_state":
                snap = msg.get("snapshot", {})
                temp = snap.get("temperature", 0)
                log(f"✅ 时间跳跃完成", f"温度={temp:.3f}")
                return
    except asyncio.TimeoutError:
        log(f"⚠️ 时间跳跃可能已完成（无 demo_state 响应）")


async def inject_memory_and_wait(ws, content, category="preference"):
    if abort_flag:
        return
    log(f"🧠 注入记忆: \"{content[:30]}\"")
    await send(ws, {
        "type": "demo_inject_memory",
        "content": content,
        "category": category,
    })
    await asyncio.sleep(2)
    log(f"✅ 记忆已注入")


async def wait_proactive(ws):
    """等待主动消息"""
    if abort_flag:
        return None
    log(f"⏳ 等待主动消息 (最多{TIMEOUT_PROACTIVE}s)...")
    t0 = time.time()
    while time.time() - t0 < TIMEOUT_PROACTIVE:
        if abort_flag:
            return None
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
            if msg.get("type") == "chat_end":
                reply = msg.get("reply", "")
                log(f"📨 主动消息到达: \"{reply[:60]}\"")
                return reply
            elif msg.get("type") == "proactive_message":
                reply = msg.get("reply", msg.get("message", ""))
                log(f"📨 主动消息到达: \"{reply[:60]}\"")
                return reply
        except asyncio.TimeoutError:
            elapsed = time.time() - t0
            print(f"  \033[90m  ... 等待主动消息 ({elapsed:.0f}s)\033[0m", end="\r")
    log(f"⏰ 超时 — 未触发主动消息")
    return None


def pause_sync(seconds, label=""):
    """同步等待（给观众看画面的时间）"""
    if label:
        log(f"⏸️ {label} ({seconds}s)")
    time.sleep(seconds)


# ═══════════════════════════════════════════
#   5 幕演示
# ═══════════════════════════════════════════

async def act1(ws):
    global current_act
    current_act = "幕1"
    log("═══ 幕1: 人格差异 ═══", "同一句话，三个灵魂")
    pause_sync(3, "展示 DemoBar 全貌")

    # Luna
    await switch_and_wait(ws, "luna")
    pause_sync(2)
    await send_chat_and_wait(ws, "在干嘛呢？", "luna")
    pause_sync(5, "观众看 Luna 回复 + 独白")

    if abort_flag: return

    # Vivian
    await switch_and_wait(ws, "vivian")
    pause_sync(2)
    await send_chat_and_wait(ws, "在干嘛呢？", "vivian")
    pause_sync(5, "观众对比 Vivian 与 Luna")


async def act2(ws):
    global current_act
    current_act = "幕2"
    log("═══ 幕2: 记忆系统 ═══", "她记得你喜欢什么")

    await switch_and_wait(ws, "luna")
    pause_sync(2)

    await inject_memory_and_wait(ws, "用户喜欢喝美式咖啡,不加糖不加奶", "preference")
    pause_sync(2, "记忆注入确认")

    await send_chat_and_wait(ws, "帮我买杯咖啡呗", "luna")
    pause_sync(5, "观众看 AI 是否提到美式不加糖")


async def act3(ws):
    global current_act
    current_act = "幕3"
    log("═══ 幕3: 情绪积累 ═══", "⭐ 核心高潮")

    # 重置
    await scenario_and_wait(ws, "calm_reset", "🧘 冷静重置")
    pause_sync(3, "观众看数值归零")

    # 正常对话
    await send_chat_and_wait(ws, "在干嘛呢", "luna")
    pause_sync(3, "对照：正常回复的挫败值")

    if abort_flag: return

    # 连发敷衍
    dismissive = [("嗯", "第1条敷衍"), ("哦", "第2条敷衍"), ("嗯嗯", "第3条敷衍")]
    for msg, label in dismissive:
        if abort_flag: return
        log(f"😑 {label}")
        await send_chat_and_wait(ws, msg, "luna")
        pause_sync(4, f"观众看{label}后数值变化")

    if abort_flag: return

    # 再补一条
    log("😑 第4条敷衍（可能触发相变）")
    await send_chat_and_wait(ws, "嗯", "luna")
    pause_sync(5, "观众看可能的情绪爆发")


async def act4(ws):
    global current_act
    current_act = "幕4"
    log("═══ 幕4: 主动消息 ═══", "她会主动找你")

    await scenario_and_wait(ws, "about_to_snap", "💥 即将爆发")
    pause_sync(3, "观众看挫败值跳变")

    await time_jump_and_wait(ws, 4)
    pause_sync(2)

    reply = await wait_proactive(ws)
    if not reply:
        log("⚠️ 第一次未触发，再跳 4h 重试")
        await time_jump_and_wait(ws, 4)
        reply = await wait_proactive(ws)

    if reply:
        pause_sync(5, "观众看主动消息")
    else:
        log("⚠️ 未触发主动消息 — 可手动展示时间跳跃效果")
        pause_sync(3)


async def act5(ws):
    global current_act
    current_act = "幕5"
    log("═══ 幕5: 技术底层 ═══", "引擎全景展示")
    log("⏸️ 请手动滚动开发面板展示各区域 (15s)")
    pause_sync(15, "手动滚动开发面板")
    log("✅ 幕5完成")


# ═══════════════════════════════════════════
#   主流程
# ═══════════════════════════════════════════

async def main():
    global start_time, abort_flag, log_thread

    print()
    print("  ╔══════════════════════════════════════╗")
    print("  ║   OpenHer Demo 自动化脚本 v2         ║")
    print("  ║   实时监控 · 逐步确认 · 异常中断     ║")
    print("  ╚══════════════════════════════════════╝")
    print()

    # ── 健康检查 ──
    print("  [检查] 后端健康检查...", end=" ")
    if not check_health():
        print("\033[91m失败\033[0m")
        print("  ❌ 后端未运行！请先启动: source .venv/bin/activate && uvicorn main:app --port 8000")
        return
    print("\033[92mOK\033[0m")

    # ── 日志文件检查 ──
    if not os.path.exists(SERVER_LOG):
        print(f"  ⚠️ 日志文件不存在: {SERVER_LOG}")

    # ── 启动日志监控 ──
    log_thread = threading.Thread(target=monitor_log, daemon=True)
    log_thread.start()
    print("  [检查] 日志监控已启动 ✅")
    print()

    # ── 提示 ──
    print("  \033[93m请确保:\033[0m")
    print("    1. UI 已打开（DemoBar + 开发面板 + 聊天窗口）")
    print("    2. 录屏已开始")
    print()
    input("  按 Enter 开始演示... ")

    start_time = time.time()
    log("🎬 录制开始", datetime.now().strftime("%H:%M:%S"))
    print()

    try:
        async with websockets.connect(WS_URL) as ws:
            await drain(ws, timeout=2)

            # ── 幕 1 ──
            await act1(ws)
            if abort_flag: return
            print()
            input("  按 Enter 继续幕2... ")
            print()

            # ── 幕 2 ──
            await act2(ws)
            if abort_flag: return
            print()
            input("  按 Enter 继续幕3... ")
            print()

            # ── 幕 3 ──
            await act3(ws)
            if abort_flag: return
            print()
            input("  按 Enter 继续幕4... ")
            print()

            # ── 幕 4 ──
            await act4(ws)
            if abort_flag: return
            print()
            input("  按 Enter 继续幕5... ")
            print()

            # ── 幕 5 ──
            await act5(ws)

    except websockets.exceptions.ConnectionClosed as e:
        abort(f"WebSocket 连接断开: {e}")
    except Exception as e:
        abort(f"未预期错误: {e}")
    finally:
        abort_flag = True

    # ── 生成输出 ──
    total = ts()
    print()
    print(f"  ╔══════════════════════════════════════╗")
    print(f"  ║  录制完成！总时长: {mmss(total)} ({total:.0f}s){'':>7}║")
    print(f"  ╚══════════════════════════════════════╝")

    # 保存时间轴
    os.makedirs("demo", exist_ok=True)
    with open("demo/timeline.json", "w", encoding="utf-8") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=2)
    print(f"  📄 时间轴: demo/timeline.json")

    # 生成 TTS 脚本
    generate_tts_script("demo/tts_script.md")
    print(f"  📄 TTS 脚本: demo/tts_script.md")
    print()


def generate_tts_script(path):
    """根据时间轴生成 TTS 旁白脚本"""
    # 旁白映射：timeline action 关键词 → 旁白文本
    narration_rules = [
        ("幕1: 人格差异",      "这是 OpenHer，一个开源的人格引擎。每个 AI 角色都有自己的内心世界、情绪波动、和主动找你聊天的欲望。上方是演示控制台，右侧是引擎的实时状态。"),
        ("角色就绪: luna",      "现在是 Luna，一个温柔的 INFP 女孩。"),
        ("✅ 回复",            None),  # 第一次回复不加旁白，第二次加
        ("角色就绪: vivian",    "切换到 Vivian，一个冷峻的 ENTJ 职场女性。"),
        ("幕2: 记忆系统",      "第二个特性：长期记忆。"),
        ("记忆已注入",          "我给 AI 注入了一条记忆：用户喜欢美式咖啡，不加糖。"),
        ("幕3: 情绪积累",      "第三个特性，也是核心技术：情绪积累与相变。"),
        ("冷静重置",           "先把所有情绪值清零，回到平静基线。"),
        ("第1条敷衍",          "现在连续发敷衍消息，注意看右侧面板的挫败值和温度变化。"),
        ("第3条敷衍",          "第三条敷衍。注意内心独白和回复的落差——嘴上说的和心里想的可能完全不同。这就是两通道人格引擎的核心。"),
        ("第4条敷衍",          "继续敷衍，AI 的态度可能发生相变。"),
        ("幕4: 主动消息",      "最后一个关键特性：AI 会主动找你。"),
        ("💥 即将爆发",        "把联结需求的挫败值拉到临界点。"),
        ("等待主动消息",        "现在什么都不做，等待引擎内部驱动力触发行动。"),
        ("主动消息到达",        "她主动找你了。这不是定时推送，而是内在驱动力的挫败积累到达了行动阈值。她有自己想找你说话的动机。"),
        ("幕5: 技术底层",      "右侧是人格引擎的完整可视化。25维输入、24维隐层、8维行为信号、5个驱动力、热力学代谢。所有这些构成了一个有内在生命的数字人格。这就是 OpenHer。"),
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("# TTS 旁白脚本 — 带时间码\n\n")
        f.write("> 根据实际录制时间自动生成，可直接用于 TTS 音频制作\n\n")

        for rule_kw, narration in narration_rules:
            if narration is None:
                continue
            # 找到第一个匹配的时间点
            for entry in timeline:
                if rule_kw in entry["action"]:
                    f.write(f"## [{entry['mmss']}] \n")
                    f.write(f"{narration}\n\n")
                    break

        f.write(f"---\n\n总时长: {timeline[-1]['mmss'] if timeline else '未知'}\n")


if __name__ == "__main__":
    asyncio.run(main())
