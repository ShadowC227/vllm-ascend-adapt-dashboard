#!/usr/bin/env bash
# 启动实时看板：每次 HTTP 请求从 vllm_board.db 读取 agents / models / benchmark_results（无需手动 export）。
#
# 用法：
#   ./run_dashboard_live.sh
#   VAA_HOST=0.0.0.0 ./run_dashboard_live.sh          # 局域网可访问
#   VLLM_BOARD_DB=/path/to/vllm_board.db ./run_dashboard_live.sh
#
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$PWD"
DB="${VLLM_BOARD_DB:-$ROOT/../vllm-ascend-adapt/vllm_board.db}"
HOST="${VAA_HOST:-127.0.0.1}"
PORT="${VAA_PORT:-8765}"
exec python3 scripts/serve_live.py --host "$HOST" --port "$PORT" --db "$DB" "$@"
