"""
OpenHer Demo 公共工具模块
========================
4 个幕脚本共用的 WS 通信、日志、注入等工具函数。
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

# Clear proxy
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
TIMEOUT_CHAT = 120
TIMEOUT_PROACTIVE = 45
CLIENT_ID = "E288419E-B214-4213-8F3D-46530823926F"

# ─── 全局状态 ───
timeline = []
start_time = 0
abort_flag = False


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
        if proc.stdout is None:
            return
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


# ─── WS 通信 ───

async def drain(ws, timeout=2):
    while True:
        try:
            await asyncio.wait_for(ws.recv(), timeout=timeout)
        except (asyncio.TimeoutError, Exception):
            break

async def send_chat_and_wait(ws, message, persona_id):
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
        if ("[feel]" in new_log and "[genome]" in new_log) or "[chat] 🤖" in new_log:
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
            frust = ""
            for line in new_log.splitlines():
                if "[drive_sat]" in line or ("frustration" in line.lower() and "con=" in line):
                    frust = line.strip()[:80]
                    break

            # Wait for multi-segment delivery to complete
            # Server logs "✂️ Delivered N segments" after all segments are sent
            if "多条拆分" in new_log or "Delivered" in new_log:
                # Multi-segment: wait for delivery confirmation
                if "Delivered" not in new_log:
                    # Keep waiting for segments to finish
                    await asyncio.sleep(1)
                    continue
                # Segments delivered — add buffer for client rendering
                await asyncio.sleep(3)

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

async def switch_tab(tab):
    """切换 DemoShowcasePanel 标签页: 1=信号 2=记忆 3=情绪 4=关系"""
    if abort_flag:
        return
    names = {1: "信号", 2: "记忆", 3: "情绪", 4: "关系"}
    log(f"📋 切换面板 → Tab {tab} ({names.get(tab, '?')})")
    inject_command("switch_tab", tab=tab)
    await asyncio.sleep(0.5)

async def set_title(title):
    """设置 DemoShowcasePanel 顶部大标题"""
    if abort_flag:
        return
    log(f"🏷️ 标题 → {title}")
    inject_command("set_title", content=title)
    await asyncio.sleep(0.3)

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


# ─── 启动 / 收尾 ───

def preflight(act_name):
    """通用启动检查"""
    global start_time
    print()
    print(f"  ╔══════════════════════════════════════╗")
    print(f"  ║   OpenHer Demo — {act_name:20s}  ║")
    print(f"  ╚══════════════════════════════════════╝")
    print()
    print("  [检查] 后端健康检查...", end=" ")
    if not check_health():
        print("\033[91m失败\033[0m")
        print("  ❌ 后端未运行！")
        sys.exit(1)
    print("\033[92mOK\033[0m")
    if os.path.exists(SERVER_LOG):
        t = threading.Thread(target=monitor_log, daemon=True)
        t.start()
        print("  [检查] 日志监控 ✅")
    print()
    input(f"  按 Enter 开始 {act_name}... ")
    start_time = time.time()
    log("🎬 开始", act_name)
    print()

def save_results(act_name):
    """保存时间轴"""
    global abort_flag
    abort_flag = True
    total = ts()
    print()
    print(f"  ╔══════════════════════════════════════╗")
    print(f"  ║  {act_name} 完成！时长: {mmss(total):>5s}{'':>12}║")
    print(f"  ╚══════════════════════════════════════╝")
    os.makedirs("demo/results", exist_ok=True)
    safe_name = act_name.replace(" ", "_").replace(":", "")
    path = f"demo/results/{safe_name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=2)
    print(f"  📄 时间轴: {path}")
    print()
