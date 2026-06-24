#!/bin/bash
# OpenHer — 一键安装脚本
# Usage: bash setup.sh

set -e

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   OpenHer — 环境安装                 ║"
echo "╚══════════════════════════════════════╝"
echo ""

# 1. Python version check (auto-detect Homebrew versions)
PYTHON=${PYTHON:-python3}
PY_MIN_MINOR=11
PY_MAX_MINOR=13
PY_VERSION=$($PYTHON --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

is_supported_python() {
    [ "$PY_MAJOR" -eq 3 ] || return 1
    [ "$PY_MINOR" -ge "$PY_MIN_MINOR" ] || return 1
    [ "$PY_MINOR" -gt "$PY_MAX_MINOR" ] && return 1
    return 0
}

if ! is_supported_python; then
    echo "⚠️  默认 Python 版本不受支持: $PY_VERSION（需要 3.11-3.13）"
    echo "   正在搜索支持版本..."
    FOUND=0
    for V in python3.13 python3.12 python3.11; do
        if command -v "$V" &>/dev/null; then
            PYTHON="$V"
            PY_VERSION=$($PYTHON --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
            PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
            PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
            echo "✅ 找到 $V ($PY_VERSION)"
            FOUND=1
            break
        fi
    done
    if [ "$FOUND" -eq 0 ]; then
        echo ""
        echo "❌ 未找到 Python 3.11-3.13，请先安装："
        echo ""
        echo "   brew install python@3.13"
        echo ""
        echo "   安装后重新运行 bash setup.sh"
        exit 1
    fi
fi
echo "✅ Python $PY_VERSION ($PYTHON)"

# 2. Virtual environment
if [ ! -d ".venv" ]; then
    echo "📦 创建虚拟环境..."
    $PYTHON -m venv .venv
    echo "✅ 虚拟环境已创建"
else
    echo "✅ 虚拟环境已存在"
fi

source .venv/bin/activate

# 3. Install dependencies
echo "📥 安装依赖..."
pip install -r requirements.txt -q
echo "✅ 依赖安装完成"

# 4. .env file
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "📝 已创建 .env（请填入你的 API 密钥）"
    else
        echo "⚠️  未找到 .env.example，请手动创建 .env"
    fi
else
    echo "✅ .env 已存在"
fi

# 5. Data directory
mkdir -p .data
echo "✅ 数据目录就绪"

# 6. Done
echo ""
echo "╔══════════════════════════════════════╗"
echo "║   ✅ 安装完成！                       ║"
echo "╠══════════════════════════════════════╣"
echo "║                                      ║"
echo "║   1. 编辑 .env 填入 API 密钥          ║"
echo "║   2. source .venv/bin/activate        ║"
echo "║   3. python main.py                   ║"
echo "║                                      ║"
echo "╚══════════════════════════════════════╝"
echo ""
