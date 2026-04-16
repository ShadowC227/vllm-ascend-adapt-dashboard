#!/usr/bin/env python3
"""
本地实时看板：静态文件 + 每次请求从 vllm_board.db 生成 /data/board.json（无需手动 export）。
JSON 含 agents、models、benchmark_results、accuracy_results（若有）、crawl_runs（若有），与库表一致。

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
from urllib.request import Request, urlopen
from urllib.error import URLError

# 保证能 import 同目录的 board_data
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from board_data import build_board_payload  # noqa: E402
from config_recommend import build_recommend_payload  # noqa: E402
from model_doc_resolve import build_model_docs_payload  # noqa: E402
from pipeline_runner import start_pipeline, get_pipeline_status, list_pipelines, stop_pipeline  # noqa: E402
from opt_utils import build_strategy_suggestion  # noqa: E402


def make_handler(root: Path, db_path: Path, project_url: str, adapt_root: Path, project_root: Path | None = None, pipeline_backend: str = ""):
    root = root.resolve()
    db_path = db_path.resolve()
    adapt_root = adapt_root.resolve()
    if project_root is None:
        project_root = db_path.parent.resolve()
    else:
        project_root = project_root.resolve()
    # pipeline_backend: 远程流水线后端地址，如 http://10.1.30.26:2242，为空则本地执行
    pipeline_backend = pipeline_backend.rstrip("/")

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

            if path == "/api/recommend":
                self._send_recommend(parsed)
                return

            if path == "/api/pipeline-status":
                self._send_pipeline_status(parsed)
                return

            if path == "/api/optimize-strategy":
                self._send_optimize_strategy(parsed)
                return

            return super().do_GET()

        def do_PUT(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"

            if path.startswith("/api/human-review/"):
                model_id = path[len("/api/human-review/"):]
                self._send_human_review_update(model_id)
                return

            if path.startswith("/api/send-back/"):
                model_id = path[len("/api/send-back/"):]
                self._send_back(model_id)
                return

            self.send_error(405, "Method Not Allowed")

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"

            if path == "/api/start-pipeline":
                self._send_start_pipeline()
                return

            if path == "/api/stop-pipeline":
                self._send_stop_pipeline()
                return

            self.send_error(405, "Method Not Allowed")

        def _send_json_response(self, body: bytes, status: int = 200, extra_headers: dict | None = None) -> None:
            """Send a JSON response with proper Content-Length header."""
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Access-Control-Allow-Origin", "*")
            if extra_headers:
                for k, v in extra_headers.items():
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _send_board_json(self) -> None:
            try:
                payload = build_board_payload(db_path, project_url, live=True)
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            except Exception as e:
                err = {"error": str(e), "meta": {"lastUpdated": ""}}
                body = json.dumps(err, ensure_ascii=False).encode("utf-8")
                self._send_json_response(body, status=500, extra_headers={"Pragma": "no-cache"})
                return

            self._send_json_response(body, extra_headers={"Pragma": "no-cache"})

        def _send_model_docs(self, parsed) -> None:
            qs = parse_qs(parsed.query, keep_blank_values=True)
            adapt_path = (qs.get("adaptPath") or [""])[0].strip()
            stem = (qs.get("stem") or [""])[0].strip()
            payload = build_model_docs_payload(adapt_root, adapt_path, stem)
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._send_json_response(body, extra_headers={"Pragma": "no-cache"})

        def _proxy_to_backend(self, method: str, api_path: str, body: bytes | None = None) -> dict | None:
            """将请求转发到远程流水线后端，返回解析后的 JSON dict，失败返回 None。"""
            if not pipeline_backend:
                return None
            url = f"{pipeline_backend}{api_path}"
            try:
                req = Request(url, data=body, method=method)
                if body is not None:
                    req.add_header("Content-Type", "application/json")
                with urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except (URLError, OSError, json.JSONDecodeError) as e:
                sys.stderr.write(f"[proxy] {method} {url} 失败: {e}\n")
                return None

        def _send_json(self, data: dict, status_code: int = 200) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self._send_json_response(body, status=status_code, extra_headers={"Pragma": "no-cache"})

        def _send_human_review_update(self, model_id: str) -> None:
            """Update human_review_status for a model (the only write op from dashboard)."""
            import sqlite3 as _sqlite3
            from datetime import datetime as _dt

            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8") if content_length else ""
                data = json.loads(body) if body else {}
            except (json.JSONDecodeError, ValueError):
                self._send_json({"error": "invalid_json"}, 400)
                return

            new_status = (data.get("status") or "").strip().lower()
            if new_status not in ("pending", "completed"):
                self._send_json({"error": "status must be 'pending' or 'completed'"}, 400)
                return

            if not model_id:
                self._send_json({"error": "model_id is required"}, 400)
                return

            try:
                conn = _sqlite3.connect(str(db_path), timeout=5)
                conn.row_factory = _sqlite3.Row
                cur = conn.cursor()
                cur.execute(
                    "SELECT human_review_status, optimization_status FROM models WHERE model_id = ?",
                    (model_id,),
                )
                row = cur.fetchone()
                if not row:
                    conn.close()
                    self._send_json({"error": f"Model '{model_id}' not found"}, 404)
                    return

                opt_status = (row["optimization_status"] or "").strip().lower()
                if opt_status != "completed":
                    conn.close()
                    self._send_json(
                        {
                            "error": f"optimization_status must be 'completed' (current: '{opt_status or 'empty'}')",
                        },
                        400,
                    )
                    return

                current_hr = (row["human_review_status"] or "").strip().lower()
                if current_hr == new_status:
                    conn.close()
                    self._send_json({"ok": True, "model_id": model_id, "human_review_status": new_status, "changed": False})
                    return

                now = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
                cur.execute(
                    "UPDATE models SET human_review_status = ?, last_updated = ? WHERE model_id = ?",
                    (new_status, now, model_id),
                )
                conn.commit()
                conn.close()
                self._send_json({"ok": True, "model_id": model_id, "human_review_status": new_status, "changed": True})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)

        def _send_back(self, model_id: str) -> None:
            """Reset a model back to a specific pipeline stage (and cascade downstream)."""
            import sqlite3 as _sqlite3
            from datetime import datetime as _dt

            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8") if content_length else ""
                data = json.loads(body) if body else {}
            except (json.JSONDecodeError, ValueError):
                self._send_json({"error": "invalid_json"}, 400)
                return

            target_stage = (data.get("target_stage") or "").strip().lower()
            if target_stage not in ("adaptation", "benchmark", "optimization"):
                self._send_json({"error": "target_stage must be 'adaptation', 'benchmark', or 'optimization'"}, 400)
                return

            if not model_id:
                self._send_json({"error": "model_id is required"}, 400)
                return

            try:
                conn = _sqlite3.connect(str(db_path), timeout=5)
                conn.row_factory = _sqlite3.Row
                cur = conn.cursor()
                cur.execute(
                    "SELECT status, benchmark_status, optimization_status, human_review_status FROM models WHERE model_id = ?",
                    (model_id,),
                )
                row = cur.fetchone()
                if not row:
                    conn.close()
                    self._send_json({"error": f"Model '{model_id}' not found"}, 404)
                    return

                adapt_st = (row["status"] or "").strip().lower()
                bench_st = (row["benchmark_status"] or "").strip().lower()
                opt_st = (row["optimization_status"] or "").strip().lower()

                # Preceding stage guard
                if target_stage == "benchmark" and adapt_st != "completed":
                    conn.close()
                    self._send_json({"error": f"adaptation must be completed first (current: {adapt_st or 'empty'})"}, 400)
                    return
                if target_stage == "optimization" and (adapt_st != "completed" or bench_st != "completed"):
                    conn.close()
                    self._send_json({"error": "both adaptation and benchmark must be completed first"}, 400)
                    return

                # No-op guard
                stage_map = {
                    "adaptation": [adapt_st, bench_st, opt_st],
                    "benchmark": [bench_st, opt_st],
                    "optimization": [opt_st],
                }
                relevant = stage_map[target_stage]
                if all(s in ("pending", "") for s in relevant):
                    conn.close()
                    self._send_json({"error": "nothing to reset: stages are already pending"}, 409)
                    return

                now = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
                reset_note = f"[打回到{target_stage} {now}] "
                reset_stages = []

                cur.execute("BEGIN IMMEDIATE")

                if target_stage == "adaptation":
                    cur.execute(
                        "UPDATE models SET status='pending', owner='', started_at='', last_updated=?, notes=? || COALESCE(notes,'') WHERE model_id=?",
                        (now, reset_note, model_id),
                    )
                    reset_stages.append("status")
                    # fall through to reset benchmark/optimization/human_review

                if target_stage in ("adaptation", "benchmark"):
                    cur.execute(
                        "UPDATE models SET benchmark_status='pending', benchmark_owner='', benchmark_started_at='', benchmark_last_updated=?, benchmark_notes=? || COALESCE(benchmark_notes,'') WHERE model_id=?",
                        (now, reset_note, model_id),
                    )
                    reset_stages.append("benchmark_status")
                    # 清理精度对齐数据
                    cur.execute("DELETE FROM accuracy_results WHERE model_id=?", (model_id,))
                    reset_stages.append("accuracy_results")
                    # fall through to reset optimization/human_review

                if target_stage in ("adaptation", "benchmark", "optimization"):
                    cur.execute(
                        "UPDATE models SET optimization_status='pending', optimization_owner='', optimization_started_at='', optimization_last_updated=?, optimization_notes=? || COALESCE(optimization_notes,'') WHERE model_id=?",
                        (now, reset_note, model_id),
                    )
                    reset_stages.append("optimization_status")
                    cur.execute(
                        "UPDATE models SET human_review_status='pending' WHERE model_id=?",
                        (model_id,),
                    )
                    reset_stages.append("human_review_status")

                conn.commit()
                conn.close()
                self._send_json({"ok": True, "model_id": model_id, "target_stage": target_stage, "reset_stages": reset_stages})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)

        def _send_start_pipeline(self) -> None:
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8") if content_length else ""
                data = json.loads(body) if body else {}
            except (json.JSONDecodeError, ValueError):
                self._send_json({"error": "invalid_json"}, 400)
                return

            model_id = data.get("model_id", "").strip()
            chips_str = data.get("chips", "4")
            mode = data.get("mode", "full").strip()

            if not model_id:
                self._send_json({"error": "model_id is required"}, 400)
                return

            try:
                chips = int(chips_str)
            except ValueError:
                chips = 4

            if mode not in ("full", "adaptation", "benchmark", "optimization"):
                mode = "full"

            # 远程代理模式
            if pipeline_backend:
                proxy_body = json.dumps({"model_id": model_id, "chips": chips, "mode": mode}).encode("utf-8")
                result = self._proxy_to_backend("POST", "/api/start-pipeline", proxy_body)
                if result is not None:
                    self._send_json(result)
                    return
                self._send_json({"error": f"远程后端 {pipeline_backend} 不可达"}, 502)
                return

            try:
                result = start_pipeline(project_root, model_id, chips, mode, db_path)
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
                return

            self._send_json(result)

        def _send_stop_pipeline(self) -> None:
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8") if content_length else ""
                data = json.loads(body) if body else {}
            except (json.JSONDecodeError, ValueError):
                self._send_json({"error": "invalid_json"}, 400)
                return

            task_id = data.get("task_id", "").strip()
            if not task_id:
                self._send_json({"error": "task_id is required"}, 400)
                return

            # 远程代理模式
            if pipeline_backend:
                proxy_body = json.dumps({"task_id": task_id}).encode("utf-8")
                result = self._proxy_to_backend("POST", "/api/stop-pipeline", proxy_body)
                if result is not None:
                    self._send_json(result)
                    return
                self._send_json({"error": f"远程后端 {pipeline_backend} 不可达"}, 502)
                return

            result = stop_pipeline(task_id)
            self._send_json(result)

        def _send_pipeline_status(self, parsed) -> None:
            qs = parse_qs(parsed.query, keep_blank_values=True)
            task_id = (qs.get("task_id") or [""])[0].strip()

            # 远程代理模式
            if pipeline_backend:
                api_path = f"/api/pipeline-status?task_id={task_id}" if task_id else "/api/pipeline-status"
                result = self._proxy_to_backend("GET", api_path)
                if result is not None:
                    self._send_json(result)
                    return
                self._send_json({"error": f"远程后端 {pipeline_backend} 不可达"}, 502)
                return

            if task_id:
                result = get_pipeline_status(task_id, db_path, project_root)
            else:
                result = list_pipelines()

            self._send_json(result)

        def _send_optimize_strategy(self, parsed) -> None:
            qs = parse_qs(parsed.query, keep_blank_values=True)
            model_id = (qs.get("model") or [""])[0].strip()
            chips_str = (qs.get("chips") or [""])[0].strip()

            if not model_id:
                self._send_json({"error": "model is required"}, 400)
                return

            try:
                chip_count = int(chips_str) if chips_str else 4
            except ValueError:
                chip_count = 4

            try:
                result = build_strategy_suggestion(db_path, model_id, chip_count)
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
                return

            self._send_json(result)

        def _send_recommend(self, parsed) -> None:
            qs = parse_qs(parsed.query, keep_blank_values=True)
            model_id = (qs.get("model") or [""])[0].strip()
            chips_str = (qs.get("chips") or [""])[0].strip()
            use_case = (qs.get("use_case") or ["throughput"])[0].strip()

            try:
                chip_count = int(chips_str) if chips_str else 0
            except ValueError:
                chip_count = 0

            if not model_id or chip_count < 1:
                payload = {
                    "found": False,
                    "model_id": model_id,
                    "chip_count": chip_count,
                    "recommendation": None,
                    "config": None,
                    "launch_command": "",
                    "env_command": "",
                    "alternatives": [],
                    "warnings": ["invalid_params"],
                }
            else:
                try:
                    payload = build_recommend_payload(db_path, model_id, chip_count, use_case=use_case)
                except Exception as e:
                    payload = {
                        "found": False,
                        "model_id": model_id,
                        "chip_count": chip_count,
                        "recommendation": None,
                        "config": None,
                        "launch_command": "",
                        "env_command": "",
                        "alternatives": [],
                        "warnings": [str(e)],
                    }

            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._send_json_response(body, extra_headers={"Pragma": "no-cache"})

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
    ap.add_argument(
        "--pipeline-backend",
        default=os.environ.get("VAA_PIPELINE_BACKEND", ""),
        help="远程流水线后端地址，如 http://10.1.30.26:2242；为空则本地执行流水线",
    )
    args = ap.parse_args()

    db_path = Path(args.db).resolve()
    adapt_root = Path(args.adapt_root).resolve() if str(args.adapt_root).strip() else db_path.parent.resolve()
    if not db_path.is_file():
        print(f"警告: 数据库文件不存在: {db_path}", file=sys.stderr)
        print("请先创建/初始化 vllm_board.db，或用 --db 指定路径。", file=sys.stderr)

    Handler = make_handler(dashboard_root, db_path, args.project_url, adapt_root, db_path.parent, args.pipeline_backend)
    ThreadingHTTPServer.allow_reuse_address = True
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
