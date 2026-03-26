#!/usr/bin/env python3
"""
幕1: 人格切换 — 同一句话，三个灵魂
=====================================
证明: 三个人格是真正不同的人，不是换了个名字

操作: 「今天项目被毙了，心情很差」分别发给 Luna / Vivian / Kai
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import websockets
from demo_utils import *

MESSAGE = "今天项目被毙了，心情很差"

async def act1():
    preflight("幕1: 人格切换")

    async with websockets.connect(WS_URL) as ws:
        await drain(ws)

        log("═══ 幕1: 人格切换 ═══", "同一句话，三个灵魂")
        await set_title("人格对比")
        await switch_tab(1)  # Tab 1: 行为信号
        pause(3, "展示 DemoBar 全貌")

        # ── Luna ──
        await switch_persona(ws, "luna")
        pause(2)
        await send_chat_and_wait(ws, MESSAGE, "luna")
        pause(5, "观众看 Luna 回复 — 情感共鸣")
        if abort_flag: return

        # ── Vivian ──
        await switch_persona(ws, "vivian")
        pause(2)
        await send_chat_and_wait(ws, MESSAGE, "vivian")
        pause(5, "观众对比 Vivian — 职场复盘")
        if abort_flag: return

        # ── Kai ──
        await switch_persona(ws, "kai")
        pause(2)
        await send_chat_and_wait(ws, MESSAGE, "kai")
        pause(5, "观众对比 Kai — 直男友人")

        log("✅ 幕1完成", "三种人格对比")

    save_results("幕1_人格切换")

if __name__ == "__main__":
    asyncio.run(act1())
