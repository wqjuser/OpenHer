#!/usr/bin/env python3
"""
幕3: 记忆改变一切 — EverMemOS 记忆注入
========================================
证明: 注入的记忆被自然融入不同话题的回复中

操作: 注入3条记忆 → 聊猫(触发团子) → 聊饮料(触发咖啡) → 聊疲倦(触发跑步)
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import websockets
from demo_utils import *

MESSAGES = [
    ("团子今天又闯祸了，把我新买的数据线咬断了", "触发团子记忆"),
    ("好累啊，想喝点什么提提神", "触发咖啡记忆"),
    ("最近总是睡不好，有什么办法吗", "触发跑步记忆"),
]

async def act3():
    preflight("幕3: 记忆注入")

    async with websockets.connect(WS_URL) as ws:
        await drain(ws)

        log("═══ 幕3: 记忆改变一切 ═══", "EverMemOS 记忆注入")

        # 重置 + Luna
        await apply_scenario(ws, "calm_reset", "🧘 重置")
        await switch_persona(ws, "luna")
        pause(2)

        # ── 注入三条记忆 ──
        log("── 注入三条记忆 ──")
        await set_title("记忆注入")
        await switch_tab(2)  # Tab 2: 记忆（看胶囊亮起）
        await inject_memory(ws, "用户养了一只猫,名叫团子,经常调皮捣蛋,喜欢咬东西", "fact")
        pause(3, "🐱 团子 亮起")
        await inject_memory(ws, "用户喜欢喝美式咖啡,不加糖不加奶", "preference")
        pause(3, "☕ 美式不加糖 亮起")
        await inject_memory(ws, "用户有跑步习惯,跑完步睡眠质量会好很多", "preference")
        pause(3, "🏃 跑步 亮起")
        pause(8, "等待记忆生效")

        # ── 用不同话题触发不同记忆 ──
        for i, (msg, hint) in enumerate(MESSAGES, 1):
            if abort_flag: break
            log(f"── 话题{i}: {hint} ──")
            await set_title(f"记忆融入 · {hint}")
            await switch_tab(2)  # 留在记忆面板
            await send_chat_and_wait(ws, msg, "luna")
            pause(6, f"观众看记忆融入回复 — {hint}")

        log("✅ 幕3完成", "三个话题分别触发不同记忆")

    save_results("幕3_记忆注入")

if __name__ == "__main__":
    asyncio.run(act3())
