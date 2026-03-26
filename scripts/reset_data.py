#!/usr/bin/env python3
"""
OpenHer 数据重置脚本
====================
清除所有运行时数据，保留基因种子。
种子一旦导入 DB 就永久存在，JSON 文件可以安全删除。

Usage:
    python scripts/reset_data.py          # 清除运行时数据（保留种子）
    python scripts/reset_data.py --seed   # 从 JSON 重新导入种子（不清除数据）
"""
import glob
import json
import os
import sqlite3
import sys

# Add project root to path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from engine.genome.style_memory import ContinuousStyleMemory

DATA_DIR = os.path.join(ROOT, ".data")
DB_PATH = os.path.join(DATA_DIR, "openher.db")
GENOME_DIR = os.path.join(DATA_DIR, "genome")

# DBs to fully delete (no precious data)
DELETE_DBS = ["chat.db", "memory.db", "task.db"]

# Tables in openher.db to clear (user data only, NOT genesis_seed)
CLEAR_TABLES = ["style_memory"]

# Other files to clean
CLEANUP_FILES = ["server.log"]


def clean_data():
    """Remove runtime data while preserving genesis seeds in openher.db."""
    print("🧹 清除运行时数据...")

    # Delete secondary DBs entirely
    for fname in DELETE_DBS:
        fpath = os.path.join(DATA_DIR, fname)
        if os.path.exists(fpath):
            os.remove(fpath)
            print(f"  ✅ 已删除 {fname}")
        else:
            print(f"  ⏭️  {fname} 不存在，跳过")

    # Clear user data tables in openher.db (preserve genesis_seed!)
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        for table in CLEAR_TABLES:
            try:
                conn.execute(f"DELETE FROM {table}")
                print(f"  ✅ 已清空 openher.db → {table}")
            except sqlite3.OperationalError:
                print(f"  ⏭️  openher.db → {table} 不存在，跳过")
        conn.commit()
        conn.close()

        # Verify seeds survived
        conn = sqlite3.connect(DB_PATH)
        count = conn.execute("SELECT COUNT(*) FROM genesis_seed").fetchone()[0]
        conn.close()
        if count > 0:
            print(f"  🧬 genesis_seed 保留完好 ({count} 条)")
        else:
            print("  ⚠️  genesis_seed 为空，需要导入种子")
    else:
        print("  ⏭️  openher.db 不存在")

    # Clean log files
    for fname in CLEANUP_FILES:
        fpath = os.path.join(DATA_DIR, fname)
        if os.path.exists(fpath):
            os.remove(fpath)
            print(f"  ✅ 已删除 {fname}")

    print()


def import_seeds():
    """Import genesis seeds into openher.db.

    Source priority:
    1. persona/seeds.bin                      (compressed binary, in repo)
    2. persona/personas/*/seeds/genesis.json  (legacy JSON)
    3. .data/genome/genesis_*.json            (legacy location)
    4. DB already has seeds                   (no action needed)
    """
    import gzip
    print("🧬 导入基因种子到 DB...")

    # Priority 1: compressed binary (not human-readable)
    seeds_bin = os.path.join(ROOT, "persona", "seeds.bin")
    if os.path.isfile(seeds_bin):
        with open(seeds_bin, "rb") as f:
            data = json.loads(gzip.decompress(f.read()).decode("utf-8"))
        total = 0
        for pid in sorted(data):
            seeds = data[pid]
            ContinuousStyleMemory.save_genesis_to_db(pid, seeds, DB_PATH)
            total += len(seeds)
            print(f"  ✅ {pid}: {len(seeds)} seeds")
        print(f"\n  📊 共导入 {len(data)} 个人格, {total} 条种子")
        return True

    # Priority 2 & 3: JSON files (persona dir or .data/genome)
    seed_files = {}
    persona_dir = os.path.join(ROOT, "persona", "personas")
    if os.path.isdir(persona_dir):
        for pid in sorted(os.listdir(persona_dir)):
            genesis_path = os.path.join(persona_dir, pid, "seeds", "genesis.json")
            if os.path.isfile(genesis_path):
                seed_files[pid] = genesis_path
    for jf in sorted(glob.glob(os.path.join(GENOME_DIR, "genesis_*.json"))):
        pid = os.path.basename(jf).replace("genesis_", "").replace(".json", "")
        if pid not in seed_files:
            seed_files[pid] = jf

    if seed_files:
        total = 0
        for pid, fpath in sorted(seed_files.items()):
            with open(fpath) as f:
                seeds = json.load(f)
            ContinuousStyleMemory.save_genesis_to_db(pid, seeds, DB_PATH)
            total += len(seeds)
            print(f"  ✅ {pid}: {len(seeds)} seeds (json)")
        print(f"\n  📊 共导入 {len(seed_files)} 个人格, {total} 条种子")
        return True

    # Priority 4: DB already has seeds
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        count = conn.execute("SELECT COUNT(*) FROM genesis_seed").fetchone()[0]
        conn.close()
        if count > 0:
            print(f"  ✅ DB 中已有 {count} 条种子，无需导入")
            return True

    print("  ❌ 未找到种子源！")
    return False


def verify():
    """Verify seeds in DB."""
    print("\n🔍 验证...")
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT persona_id, length(seeds) FROM genesis_seed ORDER BY persona_id").fetchall()
    conn.close()
    for pid, size in rows:
        print(f"  {pid}: {size} chars ✅")
    print(f"\n✅ 重置完成！共 {len(rows)} 个人格种子已就绪。")
    print("   下一步: 重启后端 → bash run.sh --bg")


if __name__ == "__main__":
    seed_only = "--seed" in sys.argv

    print()
    print("╔══════════════════════════════════════╗")
    if seed_only:
        print("║   OpenHer — 重新导入种子             ║")
    else:
        print("║   OpenHer — 数据重置（保留种子）      ║")
    print("╚══════════════════════════════════════╝")
    print()

    if not seed_only:
        clean_data()

    import_seeds()
    verify()
