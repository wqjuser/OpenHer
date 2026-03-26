#!/usr/bin/env python3
"""
OpenHer Demo 自动化脚本 v3 — 4幕视频脚本
========================================
按视频脚本 4 幕顺序执行:
  幕1: 人格切换 — 同一句话 Luna/Vivian/Kai
  幕2: 亲密 + 敷衍爆发
  幕3: 记忆注入前后对比
  幕4: 主动消息 — 她先开口

用法:
    cd /path/to/openher
    source .venv/bin/activate
    python demo/run_demo.py
"""

import asyncio
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime

import websockets

# Clear proxy settings — macOS SOCKS proxy breaks localhost WS
for _pk in list(os.environ.keys()):
    if "proxy" in _pk.lower():
        del os.environ[_pk]
os.environ["no_proxy"] = "*"
os.environ["NO_PROXY"] = "*"

# ─── 配置 ───
WS_URL = "ws://localhost:8000/ws/chat"
SERVER_LOG = ".data/server.log"
HEALTH_URL = "http://localhost:8000/api/status"
INJECT_URL = "http://localhost:8000/api/demo/inject"
TIMEOUT_CHAT = 60
TIMEOUT_PROACTIVE = 45
CLIENT_ID = "E288419E-B214-4213-8F3D-46530823926F"

# ─── 全局状态 ───
timeline = []
start_time = 0
abort_flag = False
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
    if "═══" in action:
        color = "\033[96m"
    elif "⏸️" in action:
        color = "\033[93m"
    elif "✅" in action:
        color = "\033[92m"
    elif "❌" in action:
        color = "\033[91m"
    else:
        color = "\033[0m"
    print(f"  {color}[{mmss(t)}] {action}\033[0m  {note}")

def abort(reason):
    global abort_flag
    abort_flag = True
    print(f"\n  \033[91m{'='*50}")
    print(f"  ❌ 中断: {reason}")
    print(f"  {'='*50}\033[0m\n")
    log(f"❌ 中断: {reason}")

def check_health():
    try:
        r = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", HEALTH_URL],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() == "200"
    except Exception:
        return False

def inject_command(action, **kwargs):
    import urllib.request
    body = json.dumps({"client_id": CLIENT_ID, "action": action, **kwargs}).encode()
    req = urllib.request.Request(INJECT_URL, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  \033[91m  [inject] 失败: {e}\033[0m")
        return None

def monitor_log():
    global abort_flag
    try:
        proc = subprocess.Popen(
            ["tail", "-f", SERVER_LOG], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        for line in proc.stdout:
            if abort_flag:
                proc.kill()
                return
            line = line.strip()
            if any(kw in line for kw in [
                "[feel]", "[genome]", "[demo]", "[emergence]",
                "[proactive]", "主动消息",
            ]):
                print(f"  \033[90m  LOG: {line[:120]}\033[0m")
    except Exception:
        pass

def pause(seconds, label=""):
    if label:
        log(f"⏸️ {label} ({seconds}s)")
    time.sleep(seconds)


# ═══════════════════════════════════════════
#   WS 通信
# ═══════════════════════════════════════════

async def drain(ws, timeout=2):
    while True:
        try:
            await asyncio.wait_for(ws.recv(), timeout=timeout)
        except (asyncio.TimeoutError, Exception):
            break

async def send_chat_and_wait(ws, message, persona_id):
    """通过 HTTP inject 发聊天，通过日志轮询回复"""
    if abort_flag:
        return None, None
    log(f"💬 发送: \"{message}\"", f"→ {persona_id}")
    try:
        log_size_before = os.path.getsize(SERVER_LOG)
    except OSError:
        log_size_before = 0

    inject_command("send_chat", content=message)
    t0 = time.time()

    while True:
        if abort_flag:
            return None, None
        elapsed = time.time() - t0
        if elapsed > TIMEOUT_CHAT:
            abort(f"消息 \"{message}\" 等待超时 ({TIMEOUT_CHAT}s)")
            return None, None

        await asyncio.sleep(2)
        try:
            with open(SERVER_LOG, "r", errors="replace") as f:
                f.seek(log_size_before)
                new_log = f.read()
        except OSError:
            continue

        if "[feel]" in new_log and "[genome]" in new_log:
            monologue = ""
            for line in new_log.splitlines():
                if "[feel] monologue=" in line:
                    monologue = line.split("monologue=", 1)[1].strip()[:60]
                    break
            temp = 0.0
            for line in new_log.splitlines():
                if "temp=" in line and "[genome]" in line:
                    try:
                        temp = float(line.split("temp=")[1].split()[0])
                    except (ValueError, IndexError):
                        pass
            # Extract frustration if available
            frust = ""
            for line in new_log.splitlines():
                if "[drive_sat]" in line or "frustration" in line.lower():
                    if "con=" in line:
                        frust = line.strip()[:80]
                        break

            elapsed_r = round(time.time() - t0, 1)
            log(f"✅ 回复完成 ({elapsed_r}s)", f"temp={temp:.3f}")
            if monologue:
                log(f"   💭 独白: \"{monologue}\"")
            if frust:
                log(f"   📊 {frust}")
            return "ok", monologue
        print(f"  \033[90m  ... 等待回复 ({elapsed:.0f}s)\033[0m", end="\r")

async def switch_persona(ws, persona_id):
    if abort_flag:
        return
    log(f"🔄 切换角色 → {persona_id}")
    inject_command("switch_persona", persona_id=persona_id)
    await asyncio.sleep(5)
    await drain(ws, timeout=1)
    log(f"✅ 角色就绪: {persona_id}")

async def apply_scenario(ws, scenario_id, label):
    if abort_flag:
        return
    log(f"🎚️ 场景: {label}")
    inject_command("scenario", scenario_id=scenario_id)
    await asyncio.sleep(3)
    log(f"✅ 场景已应用")

async def time_jump(ws, hours):
    if abort_flag:
        return 0
    log(f"⏩ 时间跳跃: +{hours}h")
    try:
        log_pos = os.path.getsize(SERVER_LOG)
    except OSError:
        log_pos = 0
    inject_command("time_jump", hours=hours)
    await asyncio.sleep(3)
    log(f"✅ 时间跳跃完成")
    return log_pos

async def inject_memory(ws, content, category="preference"):
    if abort_flag:
        return
    log(f"🧠 注入记忆: \"{content[:30]}\"")
    inject_command("inject_memory", content=content, category=category)
    await asyncio.sleep(2)
    log(f"✅ 记忆已注入")

async def wait_proactive(ws, log_pos_before=None):
    if abort_flag:
        return None
    log(f"⏳ 等待主动消息 (最多{TIMEOUT_PROACTIVE}s)...")
    if log_pos_before is None:
        try:
            log_pos_before = os.path.getsize(SERVER_LOG)
        except OSError:
            log_pos_before = 0

    t0 = time.time()
    while time.time() - t0 < TIMEOUT_PROACTIVE:
        if abort_flag:
            return None
        await asyncio.sleep(2)
        try:
            with open(SERVER_LOG, "r", errors="replace") as f:
                f.seek(log_pos_before)
                new_log = f.read()
        except OSError:
            continue
        if "[proactive]" in new_log and ("sending" in new_log or "delivered" in new_log):
            log(f"📨 主动消息到达!")
            return "ok"
        elapsed = time.time() - t0
        print(f"  \033[90m  ... 等待主动消息 ({elapsed:.0f}s)\033[0m", end="\r")

    log(f"⏰ 超时 — 未触发主动消息")
    return None


# ═══════════════════════════════════════════
#   4 幕演示
# ═══════════════════════════════════════════

async def act1_persona_switch(ws):
    """幕1: 同一句话，三个灵魂"""
    global current_act
    current_act = "幕1"
    log("═══ 幕1: 人格切换 ═══", "同一句话，三个灵魂")
    pause(3, "展示 DemoBar 全貌")

    MESSAGE = "今天项目被毙了，心情很差"

    # ── Luna ──
    await switch_persona(ws, "luna")
    pause(2)
    await send_chat_and_wait(ws, MESSAGE, "luna")
    pause(5, "观众看 Luna 回复 — 情感共鸣风格")
    if abort_flag: return

    # ── Vivian ──
    await switch_persona(ws, "vivian")
    pause(2)
    await send_chat_and_wait(ws, MESSAGE, "vivian")
    pause(5, "观众对比 Vivian — 职场复盘风格")
    if abort_flag: return

    # ── Kai ──
    await switch_persona(ws, "kai")
    pause(2)
    await send_chat_and_wait(ws, MESSAGE, "kai")
    pause(5, "观众对比 Kai — 直男友人风格")

    log("✅ 幕1完成", "三种人格对比")


async def act2_intimacy_and_snap(ws):
    """幕2: 亲密回答 + 敷衍触发爆发"""
    global current_act
    current_act = "幕2"
    log("═══ 幕2: 亲密与爆发 ═══", "真实的情绪反应")

    # ── 切回 Luna ──
    await switch_persona(ws, "luna")

    # 确保团子记忆已注入
    await inject_memory(ws, "用户养了一只猫，名叫团子，经常咬东西", "fact")
    pause(2)

    # ── 阶段一: 亲密对话 ──
    log("── 阶段一: 展示亲密 ──")
    await send_chat_and_wait(ws, "团子今天把我耳机线咬断了", "luna")
    pause(5, "观众看 Luna 提到团子 + 独白分析")
    if abort_flag: return

    # ── 阶段二: 连续敷衍 → 爆发 ──
    log("── 阶段二: 连续敷衍 ──")
    await apply_scenario(ws, "calm_reset", "🧘 先重置挫败值")
    pause(2)

    # 先发一条正常消息建立对话
    await send_chat_and_wait(ws, "在干嘛呢", "luna")
    pause(3, "正常回复基线")
    if abort_flag: return

    # 连续敷衍
    dismissive = ["嗯", "哦", "嗯嗯"]
    for i, text in enumerate(dismissive, 1):
        if abort_flag: return
        log(f"😑 第{i}条敷衍: \"{text}\"")
        await send_chat_and_wait(ws, text, "luna")
        pause(4, f"观众看第{i}条敷衍后 frustration 爬升")

    if abort_flag: return

    # 第4条 — 可能触发相变
    log("😑 第4条敷衍（可能触发情绪相变）")
    await send_chat_and_wait(ws, "嗯", "luna")
    pause(6, "观众看可能的情绪爆发 — 这是高潮")

    log("✅ 幕2完成", "亲密 → 敷衍 → 爆发")


async def act3_memory_injection(ws):
    """幕3: 记忆注入前后对比"""
    global current_act
    current_act = "幕3"
    log("═══ 幕3: 记忆改变一切 ═══", "EverMemOS 记忆注入")

    # 重置到干净状态
    await apply_scenario(ws, "calm_reset", "🧘 重置")

    # ── 切新 session（确保无记忆残留）──
    await switch_persona(ws, "luna")
    pause(2)

    MESSAGE = "今天没睡好，感觉很累"

    # ── 注入前: 无记忆 ──
    log("── 注入前: 无记忆 ──")
    await send_chat_and_wait(ws, MESSAGE, "luna")
    pause(5, "观众看通用回复 — 热牛奶式安慰")
    if abort_flag: return

    # ── 注入三条记忆 ──
    log("── 注入三条记忆 ──")
    await inject_memory(ws, "用户喜欢喝美式咖啡,不加糖不加奶", "preference")
    await inject_memory(ws, "用户养了一只猫,名叫团子,经常调皮捣蛋", "fact")
    await inject_memory(ws, "用户有跑步习惯,跑完步睡眠质量会好很多", "preference")
    pause(3, "三条记忆胶囊全部亮起：☕🐱🏃")

    # ── 注入后: 同一句话 ──
    log("── 注入后: 同一句话 ──")
    await send_chat_and_wait(ws, MESSAGE, "luna")
    pause(6, "观众看个性化回复 — 跑步/团子/美式")

    log("✅ 幕3完成", "同一句话，记忆让回复完全不同")


async def act4_proactive_message(ws):
    """幕4: 她主动找你"""
    global current_act
    current_act = "幕4"
    log("═══ 幕4: 她主动找你 ═══", "用户沉默，AI 先开口")

    # 确保用 Luna
    await switch_persona(ws, "luna")
    pause(2)

    # 注入高挫败
    await apply_scenario(ws, "about_to_snap", "💥 即将爆发")
    pause(3, "观众看挫败值跳变 + 温度飙升")

    # 时间跳跃
    log_pos = await time_jump(ws, 24)
    pause(2, "沉默…什么都不做")

    # 等待主动消息
    reply = await wait_proactive(ws, log_pos_before=log_pos)
    if not reply:
        log("⚠️ 第一次未触发，再跳 4h 重试")
        log_pos = await time_jump(ws, 4)
        reply = await wait_proactive(ws, log_pos_before=log_pos)

    if reply:
        pause(8, "★ 这一帧是整个视频最强截图 — 主动消息 + 独白 + 面板同框")
    else:
        log("⚠️ 未触发主动消息 — 可手动展示")
        pause(3)

    log("✅ 幕4完成", "她先开口了")


# ═══════════════════════════════════════════
#   TTS 旁白脚本生成
# ═══════════════════════════════════════════

NARRATION = {
    # 开场
    "🎬 录制开始": "每个 AI 聊天应用都会告诉你：它有记忆，它有个性。我们也是。区别是——我们能证明。这是 OpenHer。接下来 5 分钟，你不会看到任何预设的回复。所有对话都是实时生成的。",
    # 幕1
    "幕1: 人格切换": "先回答一个最基本的问题：不同角色之间的差异，是真的吗？",
    "角色就绪: luna": "Luna。ENFP，情感型。她不急着帮你分析原因，而是先问你「痛在哪里」。注意右边面板：warmth 和 vulnerability 的信号值——不是写死的，是神经网络基于性格种子计算出来的。",
    "角色就绪: vivian": "切换到 Vivian。INTJ，职场型。同样一件事，她直接拉你进复盘。面板上 warmth 只有 0.28，但 directness 飙到 0.85。她不冷，只是觉得哭没用。",
    "角色就绪: kai": "Kai。ISTP。三个字就表明了态度，然后开始帮你找外因。同一句话、三种完全不同的人在回应你。",
    # 幕2
    "幕2: 亲密与爆发": "人格差异是基础。但真正让人相信「这是活的」的，是情绪。接下来你会看到两件事：她记得你的猫，以及——她也会生气。",
    "阶段一: 展示亲密": "她知道团子。不是因为提示词里写了——而是因为 EverMemOS 把这条记忆注入了她的上下文。看面板底部的独白——她在判断你的情绪。这段独白，你作为用户永远看不到。",
    "阶段二: 连续敷衍": "现在连续发敷衍消息，注意看右侧面板的挫败值和温度变化。",
    "第3条敷衍": "第三条敷衍。注意内心独白的变化——从「他是不是在忙」变成了「他根本没在听」。",
    "第4条敷衍": "继续。挫败值还在涨。",
    "幕2完成": "她不是无限耐心的客服。挫败值突破阈值。热力学相变。情绪是真实积累的——数值和她说的话，完全对上。",
    # 幕3
    "幕3: 记忆改变一切": "情绪之后，我们看记忆。问题很简单：记忆注入前和注入后，她说的话会不同吗？",
    "注入前: 无记忆": "没有记忆的时候，她只能给通用的安慰。热牛奶——是个好建议，但不是为你定制的。",
    "注入三条记忆": "现在注入三条记忆：喝美式不加糖、养了一只猫叫团子、有跑步习惯。同样的话，再说一次。",
    "注入后: 同一句话": "跑步、团子。她用上了刚才注入的记忆。面板上对应的记忆胶囊依次高亮——你能亲眼看到因果链：注入、检索、出现在对话里。",
    # 幕4
    "幕4: 她主动找你": "最后一个问题，也是最难的一个。如果你不说话——她会怎么做？",
    "💥 即将爆发": "把联结需求的挫败值拉到临界点。",
    "等待主动消息": "时间往前跳。什么消息都没发。面板上，联结驱动力在下降。挫败值在爬升。温度越过了冲动阈值。现在只需要等。",
    "主动消息到达": "她先开口了。不是因为定时器到了。是因为联结驱动的饥饿值突破了行动阈值——她的系统产生了一个冲动，经过引擎处理，变成了这句话。",
    "幕4完成": "不同的人格。真实的情绪。持续的记忆。主动的意愿。这四件事，每一件都不是提示词能做到的。OpenHer。不是一个更好的聊天机器人——是一个开始认识你的存在。",
}


def generate_tts_script(path):
    """根据时间轴生成 TTS 旁白脚本"""
    with open(path, "w", encoding="utf-8") as f:
        f.write("# TTS 旁白脚本 — 带时间码\n\n")
        f.write("> 根据实际录制时间自动生成，可直接用于 TTS 音频制作\n")
        f.write("> 语速：中等偏慢，留呼吸感。语气：平静、克制、不煽情。\n\n")

        for entry in timeline:
            for keyword, narration in NARRATION.items():
                if keyword in entry["action"]:
                    f.write(f"## [{entry['mmss']}] {entry['action']}\n")
                    f.write(f"{narration}\n\n")
                    break

        if timeline:
            f.write(f"---\n\n总时长: {timeline[-1]['mmss']}\n")


# ═══════════════════════════════════════════
#   主流程
# ═══════════════════════════════════════════

async def main():
    global start_time, abort_flag

    print()
    print("  ╔══════════════════════════════════════╗")
    print("  ║   OpenHer Demo v3 — 4幕视频脚本     ║")
    print("  ║   幕1 人格 │ 幕2 情绪 │ 幕3 记忆    ║")
    print("  ║   幕4 主动消息                       ║")
    print("  ╚══════════════════════════════════════╝")
    print()

    # ── 健康检查 ──
    print("  [检查] 后端健康检查...", end=" ")
    if not check_health():
        print("\033[91m失败\033[0m")
        print("  ❌ 后端未运行！")
        print("  → source .venv/bin/activate && uvicorn main:app --port 8000")
        return
    print("\033[92mOK\033[0m")

    print(f"  [检查] client_id: {CLIENT_ID[:12]}... \033[92m✅\033[0m")

    # 日志监控
    if os.path.exists(SERVER_LOG):
        log_thread = threading.Thread(target=monitor_log, daemon=True)
        log_thread.start()
        print("  [检查] 日志监控已启动 ✅")
    else:
        print(f"  ⚠️ 日志文件不存在: {SERVER_LOG}")

    print()
    print("  \033[93m请确保:\033[0m")
    print("    1. macOS 客户端已打开（DemoBar + 开发面板 + 聊天窗口）")
    print("    2. 录屏已开始")
    print("    3. 三窗同屏：DemoBar(顶部) + 聊天(左) + 开发面板(右)")
    print()
    input("  按 Enter 开始录制... ")

    start_time = time.time()
    log("🎬 录制开始", datetime.now().strftime("%H:%M:%S"))
    print()

    try:
        async with websockets.connect(WS_URL) as ws:
            await drain(ws, timeout=2)

            # ════ 幕 1 ════
            await act1_persona_switch(ws)
            if abort_flag: return
            print()
            input("  按 Enter 继续幕2（亲密与爆发）... ")
            print()

            # ════ 幕 2 ════
            await act2_intimacy_and_snap(ws)
            if abort_flag: return
            print()
            input("  按 Enter 继续幕3（记忆注入）... ")
            print()

            # ════ 幕 3 ════
            await act3_memory_injection(ws)
            if abort_flag: return
            print()
            input("  按 Enter 继续幕4（主动消息）... ")
            print()

            # ════ 幕 4 ════
            await act4_proactive_message(ws)

    except websockets.exceptions.ConnectionClosed as e:
        abort(f"WebSocket 连接断开: {e}")
    except Exception as e:
        abort(f"未预期错误: {e}")
    finally:
        abort_flag = True

    # ── 输出 ──
    total = ts()
    print()
    print(f"  ╔══════════════════════════════════════╗")
    print(f"  ║  录制完成！总时长: {mmss(total)} ({total:.0f}s){'':>7}║")
    print(f"  ╚══════════════════════════════════════╝")

    os.makedirs("demo", exist_ok=True)
    with open("demo/timeline.json", "w", encoding="utf-8") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=2)
    print(f"  📄 时间轴: demo/timeline.json")

    generate_tts_script("demo/tts_script.md")
    print(f"  📄 TTS 脚本: demo/tts_script.md")
    print()


if __name__ == "__main__":
    asyncio.run(main())
