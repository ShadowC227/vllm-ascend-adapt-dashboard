#!/usr/bin/env bash
# 将实时看板注册为 systemd 服务：开机自启、崩溃自动重启（持久化运行）。
#
# 用法（在看板仓库根目录执行，需 root）：
#   sudo ./deploy/install-systemd.sh
#   sudo ./deploy/install-systemd.sh --host 0.0.0.0 --port 8765
#   sudo ./deploy/install-systemd.sh --db /path/to/vllm_board.db
#
# 卸载：
#   sudo systemctl disable --now vaa-dashboard
#   sudo rm /etc/systemd/system/vaa-dashboard.service
#   sudo systemctl daemon-reload
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="/etc/systemd/system/vaa-dashboard.service"

VAA_HOST="${VAA_HOST:-0.0.0.0}"
VAA_PORT="${VAA_PORT:-8765}"
VLLM_BOARD_DB="${VLLM_BOARD_DB:-$ROOT/../vllm-ascend-adapt/vllm_board.db}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) VAA_HOST="$2"; shift 2 ;;
    --port) VAA_PORT="$2"; shift 2 ;;
    --db) VLLM_BOARD_DB="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: sudo $0 [--host 0.0.0.0] [--port 8765] [--db /path/to/vllm_board.db]"
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请使用 root 运行: sudo $0" >&2
  exit 1
fi

PYTHON="$(command -v python3)"
if [[ -z "$PYTHON" ]]; then
  echo "未找到 python3" >&2
  exit 1
fi

if [[ -f "$VLLM_BOARD_DB" ]]; then
  DB_ABS="$(cd "$(dirname "$VLLM_BOARD_DB")" && pwd)/$(basename "$VLLM_BOARD_DB")"
else
  DB_ABS="$VLLM_BOARD_DB"
  echo "注意: 数据库文件尚不存在，将仍写入该路径: $DB_ABS" >&2
fi

cat >"$OUT" <<EOF
[Unit]
Description=VAA Live Dashboard (serve_live.py, SQLite → JSON per request)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$ROOT
Environment=VAA_HOST=$VAA_HOST
Environment=VAA_PORT=$VAA_PORT
Environment=VLLM_BOARD_DB=$DB_ABS
ExecStart=$PYTHON scripts/serve_live.py
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal
SyslogIdentifier=vaa-dashboard

[Install]
WantedBy=multi-user.target
EOF

echo "已写入: $OUT"
echo "  WorkingDirectory=$ROOT"
echo "  VAA_HOST=$VAA_HOST VAA_PORT=$VAA_PORT"
echo "  VLLM_BOARD_DB=$DB_ABS"

systemctl daemon-reload
systemctl enable vaa-dashboard
systemctl restart vaa-dashboard
systemctl --no-pager -l status vaa-dashboard || true
echo ""
echo "查看日志: journalctl -u vaa-dashboard -f"
echo "停止服务: sudo systemctl stop vaa-dashboard"
