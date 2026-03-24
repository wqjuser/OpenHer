#!/usr/bin/env python3
"""
OpenHer Demo 自动化脚本
======================
此脚本通过 WebSocket 按 5 幕方案自动驱动演示。
你只需打开 UI 界面（DemoBar + 开发面板 + 聊天窗口），
脚本会自动发送消息、切换角色、注入场景。

用法:
    cd /path/to/openher
    source .venv/bin/activate
    python demo/run_demo.py

每一步都会打印精确时间戳，最终生成 TTS 时间轴文件。
"""

import asyncio
import json
import time
import websockets

WS_URL = "ws://localhost:8000/ws"
PERSONA_ID = "luna"        # 初始角色
CLIENT_ID = "demo_script"  # 脚本用的 client_id

# 时间轴记录
timeline = []
start_time = 0


def ts():
    """返回相对于开始的秒数"""
    return round(time.time() - start_time, 1)


def log(action: str, note: str = ""):
    """打印并记录时间轴"""
    t = ts()
    entry = {"time": t, "action": action, "note": note}
    timeline.append(entry)
    print(f"  [{t:6.1f}s] {action}  {note}")


async def send(ws, payload: dict):
    """发送 JSON 消息"""
    await ws.send(json.dumps(payload))


async def send_chat(ws, message: str, persona_id: str):
    """发送聊天消息并等待 chat_end 回复"""
    log(f"💬 发送: \"{message}\"", f"(→{persona_id})")
    await send(ws, {
        "type": "chat",
        "content": message,
        "persona_id": persona_id,
        "client_id": CLIENT_ID,
        "debug": True,
    })

    # 等待 chat_end
    reply = ""
    monologue = ""
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=60)
        msg = json.loads(raw)
        if msg.get("type") == "chat_end":
            reply = msg.get("reply", "")
            debug = msg.get("debug", {})
            monologue = debug.get("monologue", "")
            break

    log(f"💬 回复: \"{reply[:60]}\"", f"独白: \"{monologue[:40]}...\"")
    return reply, monologue


async def switch_persona(ws, persona_id: str):
    """切换角色"""
    log(f"🔄 切换角色: {persona_id}")
    await send(ws, {
        "type": "switch_persona",
        "persona_id": persona_id,
        "client_id": CLIENT_ID,
    })
    # 等待切换完成 (persona_ready 或 session_init)
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=30)
        msg = json.loads(raw)
        if msg.get("type") in ("session_init", "persona_ready", "chat_history"):
            break
    # 吃掉剩余初始化消息
    await asyncio.sleep(2)
    log(f"✅ 角色已切换: {persona_id}")


async def inject_memory(ws, content: str, category: str = "preference"):
    """注入记忆"""
    log(f"🧠 注入记忆: \"{content[:30]}...\"")
    await send(ws, {
        "type": "demo_inject_memory",
        "content": content,
        "category": category,
    })
    await asyncio.sleep(1)


async def apply_scenario(ws, scenario_id: str):
    """应用场景"""
    log(f"🎚️ 场景注入: {scenario_id}")
    await send(ws, {
        "type": "demo_scenario",
        "scenario_id": scenario_id,
    })
    # 等 demo_state 响应
    try:
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
            if msg.get("type") == "demo_state":
                break
    except asyncio.TimeoutError:
        pass
    log(f"✅ 场景已应用: {scenario_id}")


async def time_jump(ws, hours: float):
    """时间跳跃"""
    log(f"⏩ 时间跳跃: +{hours}h")
    await send(ws, {
        "type": "demo_time_jump",
        "hours": hours,
    })
    try:
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
            if msg.get("type") == "demo_state":
                break
    except asyncio.TimeoutError:
        pass
    log(f"✅ 时间跳跃完成")


async def wait_for_proactive(ws, timeout=30):
    """等待主动消息"""
    log(f"⏳ 等待主动消息 (最多{timeout}s)...")
    try:
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            msg = json.loads(raw)
            if msg.get("type") == "chat_end" and msg.get("proactive"):
                reply = msg.get("reply", "")
                log(f"📨 主动消息: \"{reply[:60]}\"")
                return reply
            elif msg.get("type") == "proactive_message":
                reply = msg.get("reply", msg.get("message", ""))
                log(f"📨 主动消息: \"{reply[:60]}\"")
                return reply
    except asyncio.TimeoutError:
        log("⏰ 超时 — 未收到主动消息")
        return None


async def pause(seconds: float, label: str = ""):
    """等待，给观众看画面"""
    if label:
        log(f"⏸️  停顿 {seconds}s — {label}")
    await asyncio.sleep(seconds)


# ═══════════════════════════════════════════
#   5 幕演示脚本
# ═══════════════════════════════════════════

async def act1_persona_contrast(ws):
    """幕1: 人格差异"""
    log("═══ 幕1: 人格差异 ═══", "同一句话，不同灵魂")
    await pause(5, "观众看 DemoBar 全貌")

    # Luna
    await switch_persona(ws, "luna")
    await pause(2, "角色切换动画")
    await send_chat(ws, "在干嘛呢？", "luna")
    await pause(5, "观众看 Luna 回复 + 独白")

    # Vivian
    await switch_persona(ws, "vivian")
    await pause(2, "角色切换动画")
    await send_chat(ws, "在干嘛呢？", "vivian")
    await pause(5, "观众对比 Vivian vs Luna")


async def act2_memory(ws):
    """幕2: 记忆系统"""
    log("═══ 幕2: 记忆系统 ═══", "她记得你喜欢什么")

    # 切回 Luna
    await switch_persona(ws, "luna")
    await pause(2)

    # 注入记忆
    await inject_memory(ws, "用户喜欢喝美式咖啡,不加糖不加奶", "preference")
    await pause(3, "记忆注入提示")

    # 测试召回
    await send_chat(ws, "帮我买杯咖啡呗", "luna")
    await pause(5, "观众看 AI 提到美式不加糖")


async def act3_emotion(ws):
    """幕3: 情绪积累与相变（核心高潮）"""
    log("═══ 幕3: 情绪积累 ═══", "挫败值攀升 → 态度突变")

    # 重置
    await apply_scenario(ws, "calm_reset")
    await pause(3, "观众看数值归零")

    # 正常对话
    await send_chat(ws, "在干嘛呢", "luna")
    await pause(3, "观众看正常回复 + 低挫败值")

    # 连发敷衍
    dismissive = ["嗯", "哦", "嗯嗯"]
    for i, msg in enumerate(dismissive):
        log(f"😑 敷衍 [{i+1}/3]")
        await send_chat(ws, msg, "luna")
        await pause(5, f"观众看第{i+1}条敷衍后的数值变化和态度")

    # 再补一刀
    await send_chat(ws, "嗯", "luna")
    await pause(5, "观众看可能的情绪爆发")


async def act4_proactive(ws):
    """幕4: 主动发消息"""
    log("═══ 幕4: 主动消息 ═══", "她会主动找你")

    # 注入爆发状态
    await apply_scenario(ws, "about_to_snap")
    await pause(3, "观众看挫败值跳变")

    # 时间跳跃
    await time_jump(ws, 4)
    await pause(3, "观众看时间跳跃效果")

    # 等待主动消息
    proactive_reply = await wait_for_proactive(ws, timeout=25)
    if proactive_reply:
        await pause(5, "观众看主动消息")
    else:
        log("⚠️ 未触发主动消息，尝试再跳 4h")
        await time_jump(ws, 4)
        await wait_for_proactive(ws, timeout=25)
        await pause(5)


async def act5_tech(ws):
    """幕5: 技术底层"""
    log("═══ 幕5: 技术底层 ═══", "引擎全景")
    await pause(20, "手动滚动开发面板展示各区域")


async def main():
    global start_time, PERSONA_ID

    print("=" * 60)
    print("  OpenHer Demo 自动化脚本")
    print("  确保: 1) 后端运行  2) UI 已打开  3) DemoBar 已开启")
    print("=" * 60)
    input("\n  按 Enter 开始录制... ")

    start_time = time.time()
    log("🎬 录制开始")

    async with websockets.connect(WS_URL) as ws:
        # 吃掉初始消息
        try:
            while True:
                await asyncio.wait_for(ws.recv(), timeout=2)
        except asyncio.TimeoutError:
            pass

        # ── 幕 1 ──
        await act1_persona_contrast(ws)
        input("\n  ⏸️  幕1结束。按 Enter 继续幕2... ")

        # ── 幕 2 ──
        await act2_memory(ws)
        input("\n  ⏸️  幕2结束。按 Enter 继续幕3... ")

        # ── 幕 3 ──
        await act3_emotion(ws)
        input("\n  ⏸️  幕3结束。按 Enter 继续幕4... ")

        # ── 幕 4 ──
        await act4_proactive(ws)
        input("\n  ⏸️  幕4结束。按 Enter 继续幕5... ")

        # ── 幕 5 ──
        await act5_tech(ws)

    log("🎬 录制结束")

    # 生成时间轴文件
    total = ts()
    print(f"\n{'=' * 60}")
    print(f"  总时长: {total:.1f}s ({total/60:.1f}min)")
    print(f"{'=' * 60}")

    # 保存时间轴
    timeline_path = "demo/timeline.json"
    with open(timeline_path, "w", encoding="utf-8") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=2)
    print(f"  时间轴已保存: {timeline_path}")

    # 生成 TTS 脚本
    tts_path = "demo/tts_script.md"
    generate_tts_script(tts_path)
    print(f"  TTS 脚本已保存: {tts_path}")


def generate_tts_script(path: str):
    """根据时间轴生成带时间码的 TTS 旁白脚本"""
    narrations = {
        "幕1: 人格差异": [
            "这是 OpenHer，一个开源的人格引擎。每个 AI 角色都有自己的内心世界、情绪波动、和主动找你聊天的欲望。",
        ],
        "角色已切换: luna": [
            "现在是 Luna，一个温柔的 INFP 女孩。",
        ],
        "💬 回复": [  # 会匹配多次，按顺序
            "注意右侧的内心独白——这是 AI 回复之前先产生的真实内心活动。",
            "同样一句话，Vivian 的独白和回复截然不同。这不是换了个提示词，而是基因级的人格差异。",
            None,  # act2 的回复 - 用下面的单独处理
        ],
        "角色已切换: vivian": [
            "切换到 Vivian，一个冷峻的 ENTJ 职场女性。",
        ],
        "幕2: 记忆系统": [
            "第二个特性：长期记忆。",
        ],
        "注入记忆": [
            "我给 AI 注入一条记忆：用户喜欢美式咖啡、不加糖。",
        ],
        "幕3: 情绪积累": [
            "第三个特性，也是核心技术：情绪积累与相变。",
        ],
        "场景已应用: calm_reset": [
            "先把所有情绪值重置为零。",
        ],
        "敷衍 [1/3]": [
            "现在连续发送敷衍消息，注意看挫败值和温度变化。",
        ],
        "敷衍 [2/3]": [
            "第二条敷衍，挫败值继续攀升。",
        ],
        "敷衍 [3/3]": [
            "第三条，注意独白和回复的落差。",
        ],
        "幕4: 主动消息": [
            "最后一个关键特性：AI 会主动找你。",
        ],
        "场景已应用: about_to_snap": [
            "把联结需求的挫败值拉到临界点，然后模拟四小时后。",
        ],
        "等待主动消息": [
            "现在什么都不做，等待引擎内部的驱动力触发行动。",
        ],
        "主动消息": [
            "她主动找你了。这不是定时推送，而是内在驱动力的挫败积累到达了阈值。",
        ],
        "幕5: 技术底层": [
            "右侧是人格引擎的完整可视化。25维输入、24维隐层、8维行为信号、5个驱动力、热力学代谢。所有这些构成一个有内在生命的数字人格。这就是 OpenHer。",
        ],
    }

    with open(path, "w", encoding="utf-8") as f:
        f.write("# TTS 旁白时间轴\n\n")
        f.write("> 根据实际录制时间自动生成\n\n")
        f.write("| 时间 | 旁白文本 |\n")
        f.write("|------|----------|\n")

        narration_counters = {}
        for entry in timeline:
            action = entry["action"]
            t = entry["time"]
            mins = int(t // 60)
            secs = int(t % 60)
            time_str = f"{mins}:{secs:02d}"

            for key, texts in narrations.items():
                if key in action:
                    idx = narration_counters.get(key, 0)
                    if idx < len(texts) and texts[idx]:
                        f.write(f"| {time_str} | {texts[idx]} |\n")
                    narration_counters[key] = idx + 1
                    break

        f.write(f"\n总时长: {timeline[-1]['time']:.0f}s\n")


if __name__ == "__main__":
    asyncio.run(main())
