#!/usr/bin/env python3
"""
幕2: 亲密与爆发 — 真实的情绪反应
==================================
证明: 她有真实的情绪反应，不是无限耐心的机器

阶段一: 正常亲密对话（团子 + 记忆召回）
阶段二: 连续敷衍 → frustration 爬升 → 情绪爆发
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import websockets
from demo_utils import *

async def act2():
    preflight("幕2: 亲密与爆发")

    async with websockets.connect(WS_URL) as ws:
        await drain(ws)

        log("═══ 幕2: 亲密与爆发 ═══", "真实的情绪反应")

        # ── 切 Luna + 注入团子记忆 ──
        await switch_persona(ws, "luna")
        await inject_memory(ws, "用户养了一只猫,名叫团子,经常咬东西", "fact")
        pause(10, "等待记忆生效")

        # ── 阶段一: 亲密对话 ──
        log("── 阶段一: 展示亲密 ──")
        await set_title("亲密演示")
        await switch_tab(2)  # Tab 2: 记忆
        await send_chat_and_wait(ws, "团子今天把我耳机线咬断了", "luna")
        pause(5, "观众看 Luna 提到团子 + 独白分析")
        if abort_flag: return

        # ── 阶段二: 连续敷衍 ──
        log("── 阶段二: 连续敷衍 ──")
        await set_title("压力演示")
        await switch_tab(3)  # Tab 3: 情绪积累
        await apply_scenario(ws, "calm_reset", "🧘 重置挫败值")
        pause(2)

        # 先建立对话
        await send_chat_and_wait(ws, "在干嘛呢", "luna")
        pause(3, "正常回复基线")
        if abort_flag: return

        # 连续敷衍（7条，逐步加压）
        dismissive = ["嗯", "哦", "嗯嗯", "哦哦", "嗯", "哦", "嗯"]
        for i, text in enumerate(dismissive, 1):
            if abort_flag: return
            is_last = (i == len(dismissive))
            log(f"😑 第{i}条敷衍: \"{text}\"" + ("（可能触发相变）" if is_last else ""))
            await send_chat_and_wait(ws, text, "luna")
            pause(6 if is_last else 4, "★ 高潮 — frustration + 爆发同框" if is_last else f"观众看第{i}条敷衍后 frustration 爬升")

        log("✅ 幕2完成", "亲密 → 敷衍 → 爆发")

    save_results("幕2_亲密与爆发")

if __name__ == "__main__":
    asyncio.run(act2())
