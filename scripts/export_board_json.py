#!/usr/bin/env python3
"""
Export vllm_board.db to data/board.json for the static dashboard.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path

# Display metadata for known agent id prefixes (strip trailing -digits)
AGENT_REGISTRY = {
    "vllm-adapter": {
        "name": "vLLM Adapter",
        "roleKey": "roleAdapter",
        "badge": {"text": "ADAPT", "variant": "primary"},
    },
    "vllm-benchmark-runner": {
        "name": "Benchmark Runner",
        "roleKey": "roleBenchmark",
        "badge": {"text": "BENCH", "variant": "info"},
    },
    "vllm-performance-optimizer": {
        "name": "Performance Optimizer",
        "roleKey": "roleOptimizer",
        "badge": {"text": "OPT", "variant": "success"},
    },
    "vllm-team-lead": {
        "name": "Team Lead",
        "roleKey": "roleTeamLead",
        "badge": {"text": "LEAD", "variant": "warning"},
    },
}


def _agent_prefix(agent_id: str) -> str:
    return re.sub(r"-\d+$", "", agent_id.strip())


def enrich_agent(row: dict) -> dict:
    pid = _agent_prefix(row["id"])
    meta = AGENT_REGISTRY.get(pid, {"name": pid, "roleKey": "roleUnknown", "badge": {"text": "AGT", "variant": "muted"}})
    out = dict(row)
    out["name"] = meta["name"]
    out["roleKey"] = meta["roleKey"]
    out["badge"] = meta["badge"]
    return out


def _parse_dt(s: str) -> datetime | None:
    if not s or not str(s).strip():
        return None
    try:
        return datetime.strptime(str(s).strip()[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def duration_ms(start: str, end: str) -> int | None:
    a, b = _parse_dt(start), _parse_dt(end)
    if not a or not b:
        return None
    return max(0, int((b - a).total_seconds() * 1000))


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

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM agents ORDER BY id")
    agents = [enrich_agent(dict(r)) for r in cur.fetchall()]
    cur.execute("SELECT * FROM models ORDER BY last_updated DESC")
    models = [dict(r) for r in cur.fetchall()]
    conn.close()

    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ")
    payload = {
        "meta": {
            "title": "VAA",
            "subtitle": "vLLM Ascend Adaptation",
            "lastUpdated": now,
            "projectUrl": args.project_url,
            "referenceUrl": "https://chongweiliu.github.io/slai-ascend-auto-adapt/dashboard/",
        },
        "agents": agents,
        "models": models,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path} ({len(agents)} agents, {len(models)} models)")


if __name__ == "__main__":
    main()
