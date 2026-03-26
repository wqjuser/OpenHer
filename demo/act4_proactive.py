#!/usr/bin/env python3
"""
幕4: 她主动找你 — 用户沉默，AI 先开口
========================================
证明: 不是你问她才答，是她真的想联系你

操作: 注入高挫败 → 时间跳跃 +24h → 等待主动消息
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import websockets
from demo_utils import *

async def act4():
    preflight("幕4: 主动消息")

    async with websockets.connect(WS_URL) as ws:
        await drain(ws)

        log("═══ 幕4: 她主动找你 ═══", "用户沉默，AI 先开口")
        await set_title("她主动找你")
        await switch_tab(4)  # Tab 4: 关系/联结驱动

        await switch_persona(ws, "luna")
        pause(2)

        # 注入高挫败
        await apply_scenario(ws, "about_to_snap", "💥 即将爆发")
        pause(3, "观众看挫败值跳变 + 温度飙升")

        # 时间跳跃
        log_pos = await time_jump(ws, 24)
        pause(2, "沉默…什么都不做")

        # 等待主动消息（只等一次，不重试以避免连发两条）
        reply = await wait_proactive(ws, log_pos_before=log_pos)
        if reply:
            pause(8, "★ 最强截图 — 主动消息 + 独白 + 面板同框")
        else:
            log("⚠️ 未触发主动消息 — 可手动展示")
            pause(3)

        log("✅ 幕4完成", "她先开口了")

    save_results("幕4_主动消息")

if __name__ == "__main__":
    asyncio.run(act4())
