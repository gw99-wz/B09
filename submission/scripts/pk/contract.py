"""Contract adapter.

The evaluator does not publish the `output_contract` field table; it only
promises that /input/case.json contains one.  We therefore *parse* whatever
shape the platform ships and never hard-code a field name.

Supported shapes
  "output_contract": ["draft_md", "sources", ...]
  "output_contract": {"fields": [...]}
  "output_contract": {"draft_md": "...", "sources": "..."}
  "output_contract": {"properties": {...}}
  "output_contract": "draft_md, sources"
"""

from __future__ import annotations

import re
from pathlib import Path

from .util import read_json

FIELD_KEYS = ("fields", "required", "properties", "outputs", "items", "schema")


def load_case(case_path) -> dict:
    return read_json(case_path)


def case_id_of(case: dict, fallback: str = "") -> str:
    for k in ("case_id", "caseId", "id", "slug", "name"):
        v = case.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return fallback


def output_fields(case: dict):
    """Return (fields, shape, raw) where fields is a list[str]."""
    raw = case.get("output_contract")
    if raw is None:
        raw = case.get("outputContract")
    if raw is None:
        return [], "absent", None

    if isinstance(raw, list):
        return [str(x) for x in raw if str(x).strip()], "list", raw

    if isinstance(raw, dict):
        for k in FIELD_KEYS:
            if k in raw:
                v = raw[k]
                if isinstance(v, list):
                    return [str(x) for x in v if str(x).strip()], f"dict.{k}.list", raw
                if isinstance(v, dict):
                    return list(v.keys()), f"dict.{k}.keys", raw
                if isinstance(v, str):
                    return _split_fields(v), f"dict.{k}.str", raw
        return list(raw.keys()), "dict.keys", raw

    if isinstance(raw, str):
        return _split_fields(raw), "str", raw

    return [], "unknown", raw


def _split_fields(s: str):
    parts = re.split(r"[,\n;]+", s)
    return [p.strip() for p in parts if p.strip()]


def material_roots(case_path, case: dict):
    """Directories to scan for materials: the case dir plus declared paths."""
    roots = []
    base = Path(case_path).resolve().parent
    roots.append(base)

    def walk(obj, depth=0):
        if depth > 6:
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str) and ("/" in v or "\\" in v) and len(v) < 300:
                    p = (base / v).resolve()
                    if p.exists():
                        roots.append(p if p.is_dir() else p.parent)
                walk(v, depth + 1)
        elif isinstance(obj, list):
            for v in obj:
                walk(v, depth + 1)

    walk(case.get("materials"))
    walk(case.get("inputs"))
    walk(case.get("assets"))
    walk(case.get("resources"))
    seen, out = set(), []
    for r in roots:
        r = Path(r).resolve()
        if r not in seen and r.exists():
            seen.add(r)
            out.append(r)
    return out
