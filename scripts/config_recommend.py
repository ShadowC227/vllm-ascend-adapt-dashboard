"""
Configuration Recommender: given a model_id and chip count, find the best
optimized benchmark configuration and reconstruct a copyable vllm serve command.

Used by serve_live.py (/api/recommend) and can also be imported directly.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from opt_utils import ENV_VAR_KEYS, METHODS_ENGINE_MAP, _parse_methods_string  # noqa: F401

# ── Config key → vllm serve CLI flag mapping ────────────────────────────────

CONFIG_TO_CLI: dict[str, str] = {
    "tensor_parallel_size": "--tensor-parallel-size",
    "gpu_memory_utilization": "--gpu-memory-utilization",
    "max_model_len": "--max-model-len",
    "max_num_batched_tokens": "--max-num-batched-tokens",
    "max_num_seqs": "--max-num-seqs",
    "enforce_eager": "--enforce-eager",
    "master_port": "--master-port",
    "trust_remote_code": "--trust-remote-code",
    "dtype": "--dtype",
    "seed": "--seed",
    "served_model_name": "--served-model-name",
    "host": "--host",
    "port": "--port",
}

# Keys inside config JSON that are NOT engine CLI flags
_SKIP_CONFIG_KEYS = ENV_VAR_KEYS | {"ascend_rt_visible_devices", "compilation_config", "model", "env"}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _is_baseline(stage: str | None) -> bool:
    """Return True if benchmark_stage looks like a baseline entry."""
    if not stage:
        return False
    return bool(re.search(r"(^|_)baseline($|_)", stage.strip().lower()))


def _parse_config_json(config_str: str | None) -> dict[str, Any]:
    """Parse the config JSON string from benchmark_results. Returns empty dict on failure."""
    if not config_str or not config_str.strip():
        return {}
    try:
        parsed = json.loads(config_str)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return {}


def _classify_config(
    config_dict: dict[str, Any],
    methods_env: dict[str, str],
    methods_engine: dict[str, Any] | None = None,
) -> tuple[dict[str, str], dict[str, Any]]:
    """
    Split a config dict into env_vars and engine_params.

    env_vars from config_dict take precedence over methods_env.
    engine_params from config_dict are merged with methods_engine (config_dict wins).
    """
    env_vars = dict(methods_env)
    engine_params = dict(methods_engine) if methods_engine else {}

    # Also check nested "env" key inside config (e.g. smolvlm2 entries)
    nested_env = config_dict.pop("env", None) if isinstance(config_dict.get("env"), dict) else None
    if nested_env:
        for k, v in nested_env.items():
            if k.upper() in ENV_VAR_KEYS or k.isupper():
                env_vars[k] = str(v)

    for key, value in config_dict.items():
        if key in ENV_VAR_KEYS or key.lower() in {k.lower() for k in ENV_VAR_KEYS}:
            env_vars[key] = str(value)
        elif key not in _SKIP_CONFIG_KEYS:
            engine_params[key] = value

    return env_vars, engine_params


def _rebuild_commands(
    model_id: str,
    config_dict: dict[str, Any],
    env_vars: dict[str, str],
    engine_params: dict[str, Any],
) -> tuple[str, str]:
    """
    Reconstruct copyable shell commands.

    Returns:
        (env_command, launch_command)
        env_command:  "export VAR1=val1 VAR2=val2 ..."
        launch_command: "vllm serve <model> --flag1 val1 ..."
    """
    # ── Environment command ──
    if env_vars:
        exports = " ".join(f"{k}={v}" for k, v in sorted(env_vars.items()))
        env_command = f"export {exports}"
    else:
        env_command = ""

    # ── Launch command ──
    # Use model path from config if available, otherwise model_id
    model_path = config_dict.get("model", model_id)

    parts = [f"vllm serve {model_path}"]

    # Engine params from the flat config dict
    for key, value in engine_params.items():
        if key in CONFIG_TO_CLI:
            flag = CONFIG_TO_CLI[key]
            if isinstance(value, bool):
                if value:
                    parts.append(flag)
            elif value is not None and value != "":
                parts.append(f"{flag} {value}")

    # Handle compilation_config separately (check both config_dict and engine_params)
    comp = config_dict.get("compilation_config") or engine_params.get("compilation_config")
    if isinstance(comp, dict):
        mode = comp.get("mode", "")
        cg_mode = comp.get("cudagraph_mode", "")
        if mode and mode != "default":
            parts.append(f"--compilation-config-mode {mode}")
        if cg_mode:
            parts.append(f"--compilation-config-cudagraph-mode {cg_mode}")

    # Handle enforce_eager from config_dict (may not be in engine_params if it was filtered)
    if config_dict.get("enforce_eager") is True and "enforce_eager" not in engine_params:
        parts.append("--enforce-eager")

    # Handle trust_remote_code
    if config_dict.get("trust_remote_code") is True and "trust_remote_code" not in engine_params:
        parts.append("--trust-remote-code")

    # Handle ascend_rt_visible_devices
    ascend_devices = config_dict.get("ascend_rt_visible_devices", "")
    if ascend_devices:
        parts.append(f"--ascend-rt-visible-devices {ascend_devices}")

    launch_command = " \\\n  ".join(parts)

    return env_command, launch_command


# ── Main entry point ────────────────────────────────────────────────────────

def build_recommend_payload(
    db_path: str | Path,
    model_id: str,
    chip_count: int,
    use_case: str = "throughput",
) -> dict[str, Any]:
    """
    Build the recommendation payload for a given model and chip count.

    Args:
        db_path: Path to vllm_board.db SQLite database.
        model_id: Model identifier (e.g. "qwen3_5_4b").
        chip_count: Number of available NPU chips.
        use_case: "throughput" (default), "latency", or "auto".

    Returns:
        A dict with keys: found, model_id, chip_count, recommendation,
        config, launch_command, env_command, alternatives, warnings.
    """
    db_path = Path(db_path).resolve()

    # ── Empty response template ──
    def _empty(found: bool, warnings: list[str]) -> dict[str, Any]:
        return {
            "found": found,
            "model_id": model_id,
            "chip_count": chip_count,
            "recommendation": None,
            "config": None,
            "launch_command": "",
            "env_command": "",
            "alternatives": [],
            "warnings": warnings,
        }

    # ── 1. Check model exists ──
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM models WHERE LOWER(model_id) = LOWER(?)", (model_id,))
    model_row = cur.fetchone()
    if not model_row:
        conn.close()
        return _empty(False, ["model_not_in_db"])

    model = dict(model_row)
    warnings: list[str] = []

    if model.get("is_moe") == 1:
        warnings.append("moe_model_note")

    # ── 2. Get benchmark results ──
    cur.execute(
        "SELECT * FROM benchmark_results WHERE LOWER(model_id) = LOWER(?) ORDER BY output_tok_per_s DESC",
        (model_id,),
    )
    all_rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    if not all_rows:
        return _empty(True, ["no_benchmark_data"] + warnings)

    # ── 3. Filter optimized entries ──
    optimized_rows = [r for r in all_rows if not _is_baseline(r.get("benchmark_stage"))]
    if not optimized_rows:
        return _empty(True, ["no_optimized_data"] + warnings)

    # ── 4. Filter by chip constraint ──
    fitting = [r for r in optimized_rows if (r.get("tensor_parallel_size") or 0) <= chip_count]
    if not fitting:
        # Provide the closest TP that exceeds the constraint as info
        min_excess = min(
            optimized_rows,
            key=lambda r: (r.get("tensor_parallel_size") or 0) - chip_count,
        )
        tp_needed = min_excess.get("tensor_parallel_size", "?")
        warnings.append(f"no_optimized_within_chips")
        return _empty(True, warnings)

    # ── 5. Select best config based on use_case ──
    if use_case == "latency":
        scheme_a_rows = [r for r in fitting if r.get("opt_scheme") == "a"]
        if scheme_a_rows:
            best = min(scheme_a_rows, key=lambda r: r.get("mean_ttft_ms") or float("inf"))
        else:
            best = min(fitting, key=lambda r: r.get("mean_ttft_ms") or float("inf"))
    elif use_case == "throughput":
        scheme_b_rows = [r for r in fitting if r.get("opt_scheme") == "b"]
        if scheme_b_rows:
            best = max(scheme_b_rows, key=lambda r: r.get("output_tok_per_s") or 0)
        else:
            best = max(fitting, key=lambda r: r.get("output_tok_per_s") or 0)
    else:  # "auto" — default, same as current behavior
        best = max(fitting, key=lambda r: r.get("output_tok_per_s") or 0)

    # ── 6. Parse the best entry ──
    config_raw = _parse_config_json(best.get("config"))
    methods_env, methods_engine, _features = _parse_methods_string(best.get("optimization_methods"))

    env_vars, engine_params = _classify_config(config_raw, methods_env, methods_engine)

    if not config_raw and not methods_env:
        warnings.append("config_missing")

    # ── 7. Rebuild commands ──
    env_command, launch_command = _rebuild_commands(model_id, config_raw, env_vars, engine_params)

    # ── 8. Build recommendation summary ──
    recommendation = {
        "tensor_parallel_size": best.get("tensor_parallel_size"),
        "output_tok_per_s": best.get("output_tok_per_s"),
        "req_per_s": best.get("req_per_s"),
        "mean_ttft_ms": best.get("mean_ttft_ms"),
        "mean_tpot_ms": best.get("mean_tpot_ms"),
        "peak_tok_per_s": best.get("peak_tok_per_s"),
        "total_tok_per_s": best.get("total_tok_per_s"),
        "optimization_methods": best.get("optimization_methods", ""),
        "chips": best.get("chips", ""),
        "notes": best.get("notes", ""),
        "opt_route": best.get("opt_route", ""),
        "opt_scheme": best.get("opt_scheme", ""),
        "opt_score": best.get("opt_score"),
        "ci_lo": best.get("ci_lo"),
        "ci_hi": best.get("ci_hi"),
    }

    # ── 9. Alternatives (other TP configs within constraint, max 3) ──
    alternatives = []
    for row in fitting:
        tp = row.get("tensor_parallel_size")
        if tp == best.get("tensor_parallel_size"):
            continue
        alternatives.append({
            "tensor_parallel_size": tp,
            "output_tok_per_s": row.get("output_tok_per_s"),
            "req_per_s": row.get("req_per_s"),
            "notes": row.get("notes", ""),
        })
    alternatives = alternatives[:3]

    return {
        "found": True,
        "model_id": model_id,
        "chip_count": chip_count,
        "recommendation": recommendation,
        "config": {
            "env_vars": env_vars,
            "engine_params": engine_params,
        },
        "launch_command": launch_command,
        "env_command": env_command,
        "alternatives": alternatives,
        "warnings": warnings,
    }
