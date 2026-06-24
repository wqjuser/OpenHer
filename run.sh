#!/bin/bash
# ──────────────────────────────────────
# OpenHer Backend · Quick Start
# Usage: ./run.sh          (foreground, see logs)
#        ./run.sh --bg     (background, logs → .data/server.log)
#        PORT=9000 ./run.sh (custom port)
# ──────────────────────────────────────

set -e
cd "$(dirname "$0")"

PORT=${PORT:-8000}
LOG_FILE=".data/server.log"
PY_MIN_MINOR=11
PY_MAX_MINOR=13
STARTUP_TIMEOUT=${STARTUP_TIMEOUT:-20}

python_is_supported() {
    "$1" -c "import sys; raise SystemExit(0 if sys.version_info[0] == 3 and $PY_MIN_MINOR <= sys.version_info[1] <= $PY_MAX_MINOR else 1)" >/dev/null 2>&1
}

find_supported_python() {
    for candidate in "${PYTHON:-python3}" python3.13 python3.12 python3.11; do
        if command -v "$candidate" >/dev/null 2>&1 && python_is_supported "$candidate"; then
            PYTHON="$candidate"
            return 0
        fi
    done
    return 1
}

install_requirements() {
    if pip install -r requirements.txt -q; then
        return 0
    fi

    echo "⚠️  依赖安装失败，尝试使用本地代理重试..."
    https_proxy=http://127.0.0.1:7890 \
        http_proxy=http://127.0.0.1:7890 \
        all_proxy=socks5://127.0.0.1:7890 \
        pip install -r requirements.txt -q
}

create_venv() {
    if ! find_supported_python; then
        echo "❌ 未找到 Python 3.11-3.13，请先安装："
        echo "   brew install python@3.13"
        exit 1
    fi

    "$PYTHON" -m venv .venv
}

# Activate venv (with executable/version validation)
VENV_PYTHON=".venv/bin/python"
if [ -d ".venv" ]; then
    if [ ! -x "$VENV_PYTHON" ] || ! "$VENV_PYTHON" -c "import sys; raise SystemExit(0 if sys.version_info[0] == 3 and $PY_MIN_MINOR <= sys.version_info[1] <= $PY_MAX_MINOR else 1)" >/dev/null 2>&1; then
        echo "⚠️  虚拟环境 Python 不可用或版本不受支持（需要 3.11-3.13）"
        echo "   尝试修复..."
        if find_supported_python && "$PYTHON" -m venv --upgrade .venv 2>/dev/null; then
            echo "✅ 虚拟环境已修复 (upgrade)"
        else
            echo "♻️  修复失败，正在重建虚拟环境..."
            rm -rf .venv
            create_venv
            source .venv/bin/activate
            install_requirements
            echo "✅ 虚拟环境已重建"
        fi
    fi
else
    echo "📦 未找到虚拟环境，正在创建..."
    create_venv
    source .venv/bin/activate
    install_requirements
    echo "✅ 虚拟环境已创建"
fi

source .venv/bin/activate

# Kill existing process on the port
PID=$(lsof -ti:$PORT 2>/dev/null || true)
if [ -n "$PID" ]; then
    kill $PID 2>/dev/null
    echo "♻️  Killed process $PID on port $PORT"
    sleep 1
fi

if [ "$1" = "--bg" ]; then
    mkdir -p "$(dirname "$LOG_FILE")"
    echo "🚀 Starting OpenHer backend on port $PORT (background)"
    echo "   Logs → $LOG_FILE"
    echo "   Stop → kill \$(lsof -ti:$PORT)"
    nohup uvicorn main:app --host 0.0.0.0 --port $PORT > "$LOG_FILE" 2>&1 &
    SERVER_PID=$!
    for _ in $(seq 1 "$STARTUP_TIMEOUT"); do
        if lsof -ti:$PORT > /dev/null 2>&1; then
            echo "✅ Backend running (PID $SERVER_PID)"
            exit 0
        fi
        if ! kill -0 "$SERVER_PID" 2>/dev/null; then
            break
        fi
        sleep 1
    done

    echo "❌ Failed to start, check $LOG_FILE"
    tail -n 80 "$LOG_FILE" 2>/dev/null || true
    exit 1
else
    echo "🚀 Starting OpenHer backend on port $PORT..."
    echo "   Press Ctrl+C to stop"
    echo ""
    uvicorn main:app --host 0.0.0.0 --port $PORT
fi
