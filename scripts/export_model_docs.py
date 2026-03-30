#!/usr/bin/env python3
"""
从 vllm_board.db 的 models 表导出各 model_id 的适配文档 JSON，供静态托管时回退读取（data/model_docs.json）。
与 serve_live 的 /api/model-docs 使用同一套路径解析（model_doc_resolve）。

用法（在看板目录下）:
  python3 scripts/export_model_docs.py
  python3 scripts/export_model_docs.py --db ../vllm-ascend-adapt/vllm_board.db --out data/model_docs.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from model_doc_resolve import build_model_docs_payload  # noqa: E402


def main() -> None:
    dashboard_root = Path(__file__).resolve().parent.parent
    default_db = dashboard_root.parent / "vllm-ascend-adapt" / "vllm_board.db"
    default_out = dashboard_root / "data" / "model_docs.json"

    ap = argparse.ArgumentParser(description="Export model adaptation markdown payloads for static dashboard fallback")
    ap.add_argument("--db", default=str(default_db))
    ap.add_argument("--adapt-root", default="", help="默认与数据库同目录父级（项目根）")
    ap.add_argument("--out", default=str(default_out))
    args = ap.parse_args()

    db_path = Path(args.db).resolve()
    adapt_root = Path(args.adapt_root).resolve() if str(args.adapt_root).strip() else db_path.parent.resolve()
    out_path = Path(args.out).resolve()

    if not db_path.is_file():
        print(f"数据库不存在: {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT model_id, adaptation_path FROM models ORDER BY model_id")
    rows = cur.fetchall()
    conn.close()

    by_stem: dict[str, dict] = {}
    for r in rows:
        mid = (r["model_id"] or "").strip()
        apath = (r["adaptation_path"] or "").strip()
        if not mid or not apath:
            continue
        by_stem[mid] = build_model_docs_payload(adapt_root, apath, mid)

    payload = {
        "meta": {
            "exportedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
            "dbPath": str(db_path),
            "adaptRoot": str(adapt_root),
        },
        "byStem": by_stem,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path} ({len(by_stem)} models)")


if __name__ == "__main__":
    main()
