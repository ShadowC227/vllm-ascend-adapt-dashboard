#!/usr/bin/env python3
"""
Export vllm_board.db to data/board.json for the static dashboard.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from board_data import build_board_payload, payload_to_json_bytes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("VLLM_BOARD_DB", "../vllm-ascend-adapt/vllm_board.db"))
    ap.add_argument("--out", default="data/board.json")
    ap.add_argument("--project-url", default="https://github.com/ShadowC227/vllm-ascend-adapt")
    args = ap.parse_args()

    db_path = Path(args.db).resolve()
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = (Path(__file__).resolve().parent.parent / out_path).resolve()

    payload = build_board_payload(db_path, args.project_url, live=False)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(payload_to_json_bytes(payload, indent=2))
    print(f"Wrote {out_path} ({len(payload['agents'])} agents, {len(payload['models'])} models)")


if __name__ == "__main__":
    main()
