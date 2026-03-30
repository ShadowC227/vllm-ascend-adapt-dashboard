#!/usr/bin/env python3
"""
本地实时看板：静态文件 + 每次请求从 vllm_board.db 生成 /data/board.json（无需手动 export）。
JSON 含 agents、models、benchmark_results（及有数据时的 accuracy_results），与库表一致。

用法（在看板目录下）:
  python3 scripts/serve_live.py
  python3 scripts/serve_live.py --port 8765 --db /path/to/vllm_board.db

浏览器打开终端里提示的地址；页面默认每 5 秒轮询刷新（可在页面里关闭或改间隔）。

另提供 GET /api/model-docs?adaptPath=adaptations/...&stem=...
优先读 {stem}.md / {stem}_cn.md；若库中路径为 adaptations/foo 而实际目录为 adaptations/foo_vllm，会自动尝试 _vllm。
若 stem 与文件名不一致（如库 model_id 为 qwen3_5_0_8b，文件为 Qwen3.5-0.8B.md），会在该目录根下匹配成对 *.md + *_cn.md。
adapt_root 默认同数据库所在项目根，可用 --adapt-root / VAA_ADAPT_ROOT 覆盖。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# 保证能 import 同目录的 board_data
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from board_data import build_board_payload  # noqa: E402
from model_doc_resolve import build_model_docs_payload  # noqa: E402


def make_handler(root: Path, db_path: Path, project_url: str, adapt_root: Path):
    root = root.resolve()
    db_path = db_path.resolve()
    adapt_root = adapt_root.resolve()

    class LiveHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"

            if path == "/data/board.json":
                self._send_board_json()
                return

            if path == "/api/model-docs":
                self._send_model_docs(parsed)
                return

            return super().do_GET()

        def _send_board_json(self) -> None:
            try:
                payload = build_board_payload(db_path, project_url, live=True)
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            except Exception as e:
                err = {"error": str(e), "meta": {"lastUpdated": ""}}
                body = json.dumps(err, ensure_ascii=False).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def _send_model_docs(self, parsed) -> None:
            qs = parse_qs(parsed.query, keep_blank_values=True)
            adapt_path = (qs.get("adaptPath") or [""])[0].strip()
            stem = (qs.get("stem") or [""])[0].strip()
            payload = build_model_docs_payload(adapt_root, adapt_path, stem)
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:
            sys.stderr.write("[%s] %s - %s\n" % (self.log_date_time_string(), self.address_string(), format % args))

        def end_headers(self) -> None:
            # 避免浏览器强缓存旧版 index.html / dashboard.js / dashboard.css，导致「改了代码页面不变」
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            low = path.lower()
            if (
                low.endswith((".html", ".js", ".css", ".mjs", ".ico", ".svg"))
                or low in ("/", "/index.html")
                or low.startswith("/api/")
            ):
                self.send_header("Cache-Control", "no-cache, must-revalidate")
            super().end_headers()

    return LiveHandler


def main() -> None:
    dashboard_root = Path(__file__).resolve().parent.parent
    default_db = dashboard_root.parent / "vllm-ascend-adapt" / "vllm_board.db"

    ap = argparse.ArgumentParser(description="VAA dashboard live server (SQLite → JSON on each request)")
    ap.add_argument("--host", default=os.environ.get("VAA_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("VAA_PORT", "8765")))
    ap.add_argument(
        "--db",
        default=os.environ.get("VLLM_BOARD_DB", str(default_db)),
        help=f"默认: {default_db}",
    )
    ap.add_argument(
        "--project-url",
        default=os.environ.get("VAA_PROJECT_URL", "https://github.com/ShadowC227/vllm-ascend-adapt"),
    )
    ap.add_argument(
        "--adapt-root",
        default=os.environ.get("VAA_ADAPT_ROOT", ""),
        help="含 adaptations/ 的 vllm-ascend-adapt 项目根目录；默认与数据库文件同目录（数据库应在项目根下）",
    )
    args = ap.parse_args()

    db_path = Path(args.db).resolve()
    adapt_root = Path(args.adapt_root).resolve() if str(args.adapt_root).strip() else db_path.parent.resolve()
    if not db_path.is_file():
        print(f"警告: 数据库文件不存在: {db_path}", file=sys.stderr)
        print("请先创建/初始化 vllm_board.db，或用 --db 指定路径。", file=sys.stderr)

    Handler = make_handler(dashboard_root, db_path, args.project_url, adapt_root)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"VAA 实时看板: http://{args.host}:{args.port}/")
    print(f"  数据库: {db_path}")
    print(f"  适配文档根目录: {adapt_root}")
    print("  按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
        server.server_close()


if __name__ == "__main__":
    main()
