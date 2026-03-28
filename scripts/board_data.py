"""
Shared: build dashboard JSON payload from vllm_board.db (used by export + live server).
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

AGENT_REGISTRY: dict[str, dict[str, Any]] = {
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


def enrich_agent(row: dict[str, Any]) -> dict[str, Any]:
    pid = _agent_prefix(row["id"])
    meta = AGENT_REGISTRY.get(
        pid,
        {"name": pid, "roleKey": "roleUnknown", "badge": {"text": "AGT", "variant": "muted"}},
    )
    out = dict(row)
    out["name"] = meta["name"]
    out["roleKey"] = meta["roleKey"]
    out["badge"] = meta["badge"]
    return out


def build_board_payload(db_path: str | Path, project_url: str, *, live: bool = False) -> dict[str, Any]:
    """
    Read SQLite and return the same structure as data/board.json.
    If live=True, meta includes dataSource hint for the frontend.
    """
    db_path = Path(db_path).resolve()
    if not db_path.is_file():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM agents ORDER BY id")
    agents = [enrich_agent(dict(r)) for r in cur.fetchall()]
    cur.execute("SELECT * FROM models ORDER BY last_updated DESC")
    models = [dict(r) for r in cur.fetchall()]

    benchmark_results: list[dict[str, Any]] = []
    benchmark_table_source: str | None = None
    accuracy_results: list[dict[str, Any]] = []
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='benchmark_results'")
    if cur.fetchone():
        cur.execute(
            "SELECT * FROM benchmark_results ORDER BY model_id, benchmark_stage, tensor_parallel_size"
        )
        benchmark_results = [dict(r) for r in cur.fetchall()]
        benchmark_table_source = "benchmark_results"
    else:
        # 若仅有名为 benchmark 的表，仍导出为 benchmark_results 供前端使用
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='benchmark'")
        if cur.fetchone():
            cur.execute("SELECT * FROM benchmark")
            benchmark_results = [dict(r) for r in cur.fetchall()]
            benchmark_table_source = "benchmark"
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='accuracy_results'")
    if cur.fetchone():
        cur.execute("SELECT * FROM accuracy_results ORDER BY model_id, dataset")
        accuracy_results = [dict(r) for r in cur.fetchall()]

    conn.close()

    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ")
    meta: dict[str, Any] = {
        "title": "VAA",
        "subtitle": "vLLM Ascend Adaptation",
        "lastUpdated": now,
        "projectUrl": project_url,
        "referenceUrl": "https://chongweiliu.github.io/slai-ascend-auto-adapt/dashboard/",
    }
    if live:
        meta["dataSource"] = "live"
        meta["dbPath"] = str(db_path)
    if benchmark_table_source:
        meta["benchmarkTableSource"] = benchmark_table_source

    return {
        "meta": meta,
        "agents": agents,
        "models": models,
        "benchmark_results": benchmark_results,
        "accuracy_results": accuracy_results,
    }


def payload_to_json_bytes(payload: dict[str, Any], *, indent: int | None = 2) -> bytes:
    text = json.dumps(payload, ensure_ascii=False, indent=indent)
    return text.encode("utf-8")
