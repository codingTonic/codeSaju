#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_PID=""
FRONTEND_PID=""
BACKEND_PID_FILE="$ROOT_DIR/.backend.pid"
FRONTEND_PID_FILE="$ROOT_DIR/.frontend.pid"
TEMP_INDEX_CREATED=false

BACKEND_PORT_EXPLICIT=false
FRONTEND_PORT_EXPLICIT=false
if [[ "${BACKEND_PORT+x}" == "x" ]]; then
    BACKEND_PORT_EXPLICIT=true
fi
if [[ "${FRONTEND_PORT+x}" == "x" ]]; then
    FRONTEND_PORT_EXPLICIT=true
fi

BACKEND_PORT=${BACKEND_PORT:-8000}
FRONTEND_PORT=${FRONTEND_PORT:-3000}
BACKEND_HOST=${BACKEND_HOST:-127.0.0.1}
FRONTEND_HOST=${FRONTEND_HOST:-127.0.0.1}
PYTHON_BIN=${PYTHON_BIN:-python3}
if [[ "$PYTHON_BIN" == "python3" && -x "$ROOT_DIR/.venv-security/bin/python" ]]; then
    PYTHON_BIN="$ROOT_DIR/.venv-security/bin/python"
fi
RUN_BACKEND=true
SELECTED_PORT=""

# Resolve PYTHON_BIN relative to project root only when a path is provided
if [[ "$PYTHON_BIN" == */* ]]; then
    if [[ "$PYTHON_BIN" != /* ]]; then
        PYTHON_BIN="$ROOT_DIR/$PYTHON_BIN"
    fi
    if [[ ! -x "$PYTHON_BIN" ]]; then
        echo "❌ '$PYTHON_BIN' 실행 파일을 찾을 수 없습니다. 경로를 확인하세요."
        exit 1
    fi
else
    if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
        echo "❌ '$PYTHON_BIN' 명령을 찾을 수 없습니다. PYTHON_BIN 환경변수를 올바른 파이썬 실행 파일로 설정하세요."
        exit 1
    fi
fi

port_is_available() {
    "$PYTHON_BIN" - "$1" "$2" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
family = socket.AF_INET6 if ":" in host else socket.AF_INET

with socket.socket(family, socket.SOCK_STREAM) as sock:
    try:
        sock.bind((host, port))
    except OSError:
        raise SystemExit(1)
PY
}

select_available_port() {
    local host="$1"
    local requested_port="$2"
    local label="$3"
    local explicit="$4"
    local candidate="$requested_port"
    local limit=$((requested_port + 100))

    if port_is_available "$host" "$requested_port"; then
        SELECTED_PORT="$requested_port"
        return
    fi

    if [[ "$explicit" == true ]]; then
        echo "❌ $label 포트 $requested_port 는 이미 사용 중입니다. 다른 포트를 지정하세요."
        exit 1
    fi

    candidate=$((candidate + 1))
    while [[ "$candidate" -lt "$limit" ]]; do
        if port_is_available "$host" "$candidate"; then
            SELECTED_PORT="$candidate"
            echo "⚠️  $label 기본 포트 $requested_port 가 사용 중이어서 $candidate 포트를 사용합니다."
            return
        fi
        candidate=$((candidate + 1))
    done

    echo "❌ $label 서버에 사용할 빈 포트를 찾지 못했습니다."
    exit 1
}

cleanup() {
    trap - EXIT INT TERM
    printf '\n🛑 서버 종료 중...\n'

    if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        kill "$BACKEND_PID" 2>/dev/null || true
        wait "$BACKEND_PID" 2>/dev/null || true
    fi

    if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        kill "$FRONTEND_PID" 2>/dev/null || true
        wait "$FRONTEND_PID" 2>/dev/null || true
    fi

    rm -f "$BACKEND_PID_FILE" "$FRONTEND_PID_FILE"

    if [[ "$TEMP_INDEX_CREATED" == true ]]; then
        rm -f "$FRONTEND_DIR/index.html"
    fi
}

trap cleanup EXIT INT TERM

echo "🚀 여울 서버 시작..."

# Start backend server when available
if [[ ! -f "$BACKEND_DIR/app/main.py" ]]; then
    echo "⚠️  백엔드 진입점을 찾을 수 없습니다: $BACKEND_DIR/app/main.py"
    echo "   프론트엔드 정적 서버만 시작합니다. 분석 API 호출은 동작하지 않습니다."
    RUN_BACKEND=false
fi

if [[ "$RUN_BACKEND" == true ]]; then
    select_available_port "$BACKEND_HOST" "$BACKEND_PORT" "백엔드" "$BACKEND_PORT_EXPLICIT"
    BACKEND_PORT="$SELECTED_PORT"
fi

select_available_port "$FRONTEND_HOST" "$FRONTEND_PORT" "프론트엔드" "$FRONTEND_PORT_EXPLICIT"
FRONTEND_PORT="$SELECTED_PORT"
CORS_ORIGINS=${CORS_ORIGINS:-"http://localhost:$FRONTEND_PORT,http://127.0.0.1:$FRONTEND_PORT"}

if [[ "$RUN_BACKEND" == true ]]; then
    echo "📡 백엔드 서버 시작 중... (포트: $BACKEND_PORT)"
    (
        cd "$BACKEND_DIR"
        if [[ -f "venv/bin/activate" ]]; then
            source venv/bin/activate
            echo "✅ 가상 환경 활성화됨"
        fi
        CORS_ORIGINS="$CORS_ORIGINS" exec "$PYTHON_BIN" -m uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" --reload --no-access-log --no-proxy-headers
    ) &
    BACKEND_PID=$!

    echo "$BACKEND_PID" > "$BACKEND_PID_FILE"
fi

echo "🌐 프론트엔드 서버 시작 중... (포트: $FRONTEND_PORT)"

if [[ ! -d "$FRONTEND_DIR" ]]; then
    echo "❌ 프론트엔드 디렉터리를 찾을 수 없습니다: $FRONTEND_DIR"
    exit 1
fi

if [[ ! -e "$FRONTEND_DIR/index.html" ]]; then
    cat <<'HTML' > "$FRONTEND_DIR/index.html"
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="0; url=app/index.html">
    <title>여울</title>
    <noscript>
        <meta http-equiv="refresh" content="0; url=app/index.html">
    </noscript>
</head>
<body>
    <p>사주 분석 페이지로 이동 중입니다. 자동으로 이동하지 않으면 <a href="app/index.html">여기를 클릭</a>하세요.</p>
</body>
</html>
HTML
    TEMP_INDEX_CREATED=true
fi

(
    cd "$ROOT_DIR"
    API_BASE=""
    if [[ "$RUN_BACKEND" == true ]]; then
        API_BASE="http://$BACKEND_HOST:$BACKEND_PORT"
    fi
    exec "$PYTHON_BIN" serve_frontend.py \
        --host "$FRONTEND_HOST" \
        --port "$FRONTEND_PORT" \
        --directory "$FRONTEND_DIR" \
        --api-base "$API_BASE"
) &
FRONTEND_PID=$!

echo "$FRONTEND_PID" > "$FRONTEND_PID_FILE"

sleep 0.4
if [[ "$RUN_BACKEND" == true ]] && ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "❌ 백엔드 서버가 시작 직후 종료되었습니다. 포트와 의존성을 확인하세요."
    exit 1
fi
if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "❌ 프론트엔드 서버가 시작 직후 종료되었습니다. 포트를 확인하세요."
    exit 1
fi

echo "✅ 서버 시작 완료!"
echo "📱 프론트엔드: http://$FRONTEND_HOST:$FRONTEND_PORT"
if [[ "$RUN_BACKEND" == true ]]; then
    echo "🔧 백엔드 API: http://$BACKEND_HOST:$BACKEND_PORT/docs"
else
    echo "🔧 백엔드 API: 시작되지 않음"
fi
echo ""
echo "⚠️  종료하려면 Ctrl+C를 누르세요"

if [[ "$RUN_BACKEND" == true ]]; then
    wait "$BACKEND_PID" "$FRONTEND_PID"
else
    wait "$FRONTEND_PID"
fi
