"""
Pipeline Runner: manage lifecycle of run_auto_team_lead.sh subprocess.

Used by serve_live.py (/api/start-pipeline, /api/pipeline-status) and can
also be imported directly.

State file: ~/.claude/pipeline_tasks/tasks.json
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

# ── Model ID fuzzy matching ────────────────────────────────────────────────

def _normalize_model_id(model_id: str) -> str:
    """Normalize a model ID for comparison: lowercase, special chars → _."""
    s = model_id.lower().strip()
    s = s.replace("/", "_").replace("-", "_").replace(".", "_")
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def resolve_model_id(db_path: Path, user_input: str) -> str | None:
    """
    Try to match *user_input* against existing model IDs in the DB.

    Matching strategy (in order):
      1. Exact case-insensitive match
      2. Exact match on normalized form (lowercase, /-. → _)
      3. Strip org prefix (e.g. "Qwen/Qwen3.5-0.8B" → "Qwen3.5-0.8B") and retry 1+2
      4. Suffix match: normalized input is a trailing substring of a normalized DB id

    Returns the original DB model_id if a match is found, else None.
    """
    if not db_path.is_file():
        return None

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT model_id FROM models")
    db_ids = [row[0] for row in cur.fetchall()]
    conn.close()

    if not db_ids:
        return None

    user_lower = user_input.strip().lower()
    user_norm = _normalize_model_id(user_input)

    # Build lookup: normalized → original
    norm_to_orig: dict[str, str] = {}
    for mid in db_ids:
        norm_to_orig[_normalize_model_id(mid)] = mid

    # 1. Exact case-insensitive
    for mid in db_ids:
        if mid.lower() == user_lower:
            return mid

    # 2. Normalized exact match
    if user_norm in norm_to_orig:
        return norm_to_orig[user_norm]

    # 3. Strip org prefix and retry
    if "/" in user_input:
        stem = user_input.rsplit("/", 1)[-1]
        stem_lower = stem.lower()
        stem_norm = _normalize_model_id(stem)
        for mid in db_ids:
            if mid.lower() == stem_lower:
                return mid
        if stem_norm in norm_to_orig:
            return norm_to_orig[stem_norm]

    # 4. Suffix match (normalized input is trailing part of some DB id)
    for norm, orig in norm_to_orig.items():
        if norm.endswith(user_norm) or user_norm.endswith(norm):
            return orig

    return None


# ── State persistence ──────────────────────────────────────────────────────

STATE_DIR = Path.home() / ".claude" / "pipeline_tasks"
STATE_FILE = STATE_DIR / "tasks.json"


def _load_tasks() -> dict[str, dict[str, Any]]:
    """Load all tasks from the state file."""
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text("utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_tasks(tasks: dict[str, dict[str, Any]]) -> None:
    """Atomically write tasks to state file."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), "utf-8")
    tmp.replace(STATE_FILE)


def _upsert_task(task: dict[str, Any]) -> None:
    """Insert or update a single task."""
    tasks = _load_tasks()
    tasks[task["task_id"]] = task
    _save_tasks(tasks)


# ── Helpers ────────────────────────────────────────────────────────────────


def _tail_lines(path: Path, n: int = 5) -> list[str]:
    """Read last *n* lines from a file (works with UTF-8 and partial reads)."""
    try:
        data = path.read_text("utf-8", errors="replace")
        lines = data.splitlines()
        return lines[-n:] if len(lines) > n else lines
    except OSError:
        return []


def _find_team_lead_log(project_root: Path) -> Path | None:
    """
    Locate today's team_lead_YYYYMMDD.log produced by run_auto_team_lead.sh.
    Returns None if not found or empty.
    """
    log_dir = project_root / "logs"
    if not log_dir.is_dir():
        return None
    today = time.strftime("%Y%m%d")
    log_path = log_dir / f"team_lead_{today}.log"
    if log_path.is_file() and log_path.stat().st_size > 0:
        return log_path
    return None


def _parse_log_exit(log_file: str) -> str:
    """Read last 1 KB of log for success / failure indicators."""
    try:
        p = Path(log_file)
        if not p.exists() or p.stat().st_size == 0:
            return "unknown"
        data = p.read_bytes()
        tail = data[-1024:].decode("utf-8", errors="replace")
        # Team-lead typically outputs these phrases on completion
        if "任务执行成功完成" in tail or "All tasks completed" in tail.lower():
            return "completed"
        if "任务执行失败" in tail or "Exit Code:" in tail:
            return "failed"
        # Check if process just ended without clear marker
        if "已停止" in tail:
            return "completed"
    except OSError:
        pass
    return "unknown"


def _query_model_status(db_path: Path, model_id: str) -> dict[str, str]:
    """Query models table for pipeline stage statuses."""
    if not db_path.is_file():
        return {}
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT status, benchmark_status, optimization_status, human_review_status "
            "FROM models WHERE LOWER(model_id) = LOWER(?)",
            (model_id,),
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return {}
        return {
            "adaptation": row["status"] or "unknown",
            "benchmark": row["benchmark_status"] or "not_started",
            "optimization": row["optimization_status"] or "not_started",
            "human_review": row["human_review_status"] or "not_started",
        }
    except Exception:
        return {}


def _is_process_alive(pid: int) -> bool:
    """Check whether a process with the given PID is still running."""
    try:
        os.kill(pid, 0)  # SIG0 = probe only
        return True
    except (ProcessLookupError, PermissionError):
        return False


# ── Public API ─────────────────────────────────────────────────────────────


def start_pipeline(
    project_root: Path,
    model_id: str,
    chips: int = 4,
    mode: str = "full",
    db_path: Path | None = None,
) -> dict[str, Any]:
    """
    Register a model and launch run_auto_team_lead.sh as a background process.

    Args:
        project_root: Path to the vllm-ascend-adapt project (contains scripts/).
        model_id: HuggingFace model identifier (e.g. "meta-llama/Meta-Llama-3-8B").
        chips: Number of available NPU chips.
        mode: Pipeline mode — "full", "adaptation", "benchmark", or "optimization".
        db_path: Path to vllm_board.db (defaults to project_root / vllm_board.db).

    Returns:
        Dict with task_id, status, log_file, pid, etc.
    """
    project_root = Path(project_root).resolve()
    db_path = Path(db_path).resolve() if db_path else project_root / "vllm_board.db"

    # ── 1. Fuzzy-match user input against existing DB model IDs ──
    resolved_id = resolve_model_id(db_path, model_id)
    if resolved_id:
        model_id = resolved_id  # use the canonical DB model_id

    # ── 2. Register model in DB (no-op if already exists) ──
    board_ops = project_root / "scripts" / "board_ops.py"
    if board_ops.is_file():
        subprocess.run(
            ["python3", str(board_ops), "register_model", "--model_id", model_id],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(project_root),
            env={**os.environ},
        )

    # ── 3. Generate task_id and log path (needed before prompt file) ──
    task_id = uuid.uuid4().hex[:8]
    log_dir = project_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"pipeline_{task_id}.log"

    # ── 4. Build environment for run_auto_team_lead.sh ──
    env = {**os.environ}
    env["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"] = "1"
    env["NODE_OPTIONS"] = "--max-old-space-size=131072"

    # run_auto_team_lead.sh resets APPEND_PROMPT="" internally and only reads
    # PROMPT_FILES or PROMPT_MODE.  Write a temp prompt file and pass via PROMPT_FILES.
    if mode == "optimization":
        from opt_utils import build_optimization_prompt  # noqa: C0415
        prompt_text = build_optimization_prompt(db_path, model_id, chips)
    else:
        prompt_text = (
            f"仅处理模型 {model_id}（可用芯片数 {chips}）。\n"
            f"如果该模型不在 pending 状态，跳过。\n完成后输出汇总。"
        )
        if mode != "full":
            mode_prompt_map = {
                "adaptation": "task_adaptation.txt",
                "benchmark": "task_benchmark.txt",
            }
            mode_file = mode_prompt_map.get(mode)
            prompts_dir = project_root / "prompts"
            if mode_file and (prompts_dir / mode_file).is_file():
                prompt_text = (prompts_dir / mode_file).read_text("utf-8") + "\n\n" + prompt_text

    prompt_file = log_dir / f"pipeline_{task_id}_prompt.txt"
    prompt_file.write_text(prompt_text, "utf-8")
    env["PROMPT_FILES"] = str(prompt_file)

    # ── 5. Launch run_auto_team_lead.sh ──
    script = project_root / "scripts" / "run_auto_team_lead.sh"
    log_fh = open(log_file, "a")  # noqa: SIM115
    try:
        proc = subprocess.Popen(
            ["bash", str(script)],
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=str(project_root),
            start_new_session=True,
        )
    except Exception:
        log_fh.close()
        raise

    # ── 6. Persist task state ──
    state: dict[str, Any] = {
        "task_id": task_id,
        "model_id": model_id,
        "chips": chips,
        "mode": mode,
        "status": "running",
        "pid": proc.pid,
        "log_file": str(log_file),
        "started_at": time.time(),
    }
    _upsert_task(state)
    return state


def get_pipeline_status(
    task_id: str,
    db_path: Path | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """
    Check the status of a pipeline task.

    Returns a dict with status, uptime, last log lines, and DB stage statuses.
    """
    tasks = _load_tasks()
    task = dict(tasks.get(task_id, {}))
    if not task:
        return {"task_id": task_id, "status": "not_found"}

    pid = task.get("pid")
    if pid and _is_process_alive(pid):
        task["status"] = "running"
    elif pid:
        task["status"] = _parse_log_exit(task.get("log_file", ""))

    task["uptime_seconds"] = int(time.time() - task.get("started_at", 0))

    # Read log lines from the team-lead's own log (not our empty wrapper)
    if project_root:
        tl_log = _find_team_lead_log(project_root)
        if tl_log:
            task["last_log_lines"] = _tail_lines(tl_log, 8)
            task["log_file"] = str(tl_log)  # expose the real log path
        else:
            # Fallback: try our wrapper log
            log_path = Path(task.get("log_file", ""))
            if log_path.exists():
                task["last_log_lines"] = _tail_lines(log_path, 8)

    # Query DB for model pipeline status
    if db_path:
        model_id = task.get("model_id", "")
        task["db_status"] = _query_model_status(db_path, model_id)

    return task


def list_pipelines() -> list[dict[str, Any]]:
    """Return all tracked pipeline tasks."""
    tasks = _load_tasks()
    now = time.time()
    result = []
    for task_id, task in tasks.items():
        entry = dict(task)
        pid = entry.get("pid")
        if pid and _is_process_alive(pid):
            entry["status"] = "running"
        elif pid and entry.get("status") == "running":
            entry["status"] = _parse_log_exit(entry.get("log_file", ""))
        entry["uptime_seconds"] = int(now - entry.get("started_at", 0))
        result.append(entry)
    # Most recent first
    result.sort(key=lambda x: x.get("started_at", 0), reverse=True)
    return result


def stop_pipeline(task_id: str) -> dict[str, Any]:
    """
    Send SIGTERM to a running pipeline process.

    Returns updated task status dict.
    """
    tasks = _load_tasks()
    task = tasks.get(task_id)
    if not task:
        return {"task_id": task_id, "status": "not_found"}

    pid = task.get("pid")
    if pid and _is_process_alive(pid):
        try:
            os.killpg(os.getpgid(pid), 15)  # SIGTERM to process group
            task["status"] = "stopping"
        except (ProcessLookupError, PermissionError):
            task["status"] = "not_found"
    else:
        task["status"] = _parse_log_exit(task.get("log_file", ""))

    _upsert_task(task)
    return task
