"""
解析 vllm-ascend-adapt 适配目录下的中英文 Markdown（与看板「适配文档」API 一致）。
供 serve_live.py 与 export_model_docs.py 共用。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def read_text_if_file(path: Path | None) -> tuple[str, bool]:
    if path is None or not path.is_file():
        return "", False
    return path.read_text(encoding="utf-8", errors="replace"), True


def norm_stem_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def pair_score(stem: str, base_without_md: str) -> int:
    if stem == base_without_md:
        return 100
    a, b = norm_stem_key(stem), norm_stem_key(base_without_md)
    if not a or not b:
        return 0
    if a == b:
        return 90
    if a in b or b in a:
        return 70
    return 0


def resolve_adapt_dir(adapt_root: Path, adapt_rel: str) -> Path | None:
    root = adapt_root.resolve()
    parts = [p for p in adapt_rel.replace("\\", "/").strip("/").split("/") if p]
    if ".." in parts or not parts:
        return None

    def as_dir(ps: list[str]) -> Path | None:
        cand = root.joinpath(*ps).resolve()
        try:
            cand.relative_to(root)
        except ValueError:
            return None
        return cand if cand.is_dir() else None

    hit = as_dir(parts)
    if hit:
        return hit
    last = parts[-1]
    if last and not str(last).endswith("_vllm"):
        hit = as_dir(parts[:-1] + [f"{last}_vllm"])
        if hit:
            return hit
    return None


def iter_root_md_pairs(adapt_dir: Path) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if not adapt_dir.is_dir():
        return out
    try:
        for p in adapt_dir.iterdir():
            if not p.is_file():
                continue
            name = p.name
            if not name.endswith("_cn.md"):
                continue
            if name.lower() == "readme_cn.md":
                continue
            core = name[: -len("_cn.md")]
            en_name = f"{core}.md"
            if (adapt_dir / en_name).is_file() and en_name.lower() != "readme.md":
                out.append((en_name, name))
    except OSError:
        pass
    return out


def resolve_model_doc_files(
    adapt_root: Path, adapt_rel: str, stem: str
) -> tuple[str, str, Path | None, Path | None]:
    default_en, default_zh = f"{stem}.md", f"{stem}_cn.md"
    adapt_dir = resolve_adapt_dir(adapt_root, adapt_rel)
    if not adapt_dir:
        return default_en, default_zh, None, None

    en_p = adapt_dir / default_en
    zh_p = adapt_dir / default_zh
    if en_p.is_file() or zh_p.is_file():
        return (
            default_en,
            default_zh,
            en_p if en_p.is_file() else None,
            zh_p if zh_p.is_file() else None,
        )

    pairs = iter_root_md_pairs(adapt_dir)
    if not pairs:
        return default_en, default_zh, None, None

    if len(pairs) == 1:
        en_n, zh_n = pairs[0]
        return en_n, zh_n, adapt_dir / en_n, adapt_dir / zh_n

    ranked: list[tuple[int, int, str, str]] = []
    for en_n, zh_n in pairs:
        base = en_n[:-3]
        ranked.append((pair_score(stem, base), len(base), en_n, zh_n))
    ranked.sort(key=lambda x: (-x[0], -x[1]))
    score, _, en_n, zh_n = ranked[0]
    if score <= 0:
        return default_en, default_zh, None, None
    return en_n, zh_n, adapt_dir / en_n, adapt_dir / zh_n


def build_model_docs_payload(adapt_root: Path, adapt_path: str, stem: str) -> dict[str, Any]:
    empty: dict[str, Any] = {
        "en": {"content": "", "exists": False},
        "zh": {"content": "", "exists": False},
        "enFile": "",
        "zhFile": "",
    }
    if not stem or any(c in stem for c in "/\\") or not (adapt_path or "").strip():
        return empty
    en_name, zh_name, en_path, zh_path = resolve_model_doc_files(adapt_root, adapt_path, stem)
    en_text, en_ok = read_text_if_file(en_path)
    zh_text, zh_ok = read_text_if_file(zh_path)
    return {
        "en": {"content": en_text, "exists": en_ok},
        "zh": {"content": zh_text, "exists": zh_ok},
        "enFile": en_name,
        "zhFile": zh_name,
    }
