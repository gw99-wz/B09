"""Emit the deliverables: parameter table, contract-mapped result.json, pack check."""

from __future__ import annotations

import os
import re
from pathlib import Path

from .util import fmt_value, write_json


def param_table_md(ledger):
    lines = [
        "# 参数表（Parameter Ledger）",
        "",
        "> 每个取值都绑定到材料 locator；`conflict` 表示材料互相矛盾，正文不得择一。",
        "",
        "| 参数 | 取值 | 单位 | 作用对象 | 状态 | 来源 |",
        "|-|-|-|-|-|-|",
    ]
    for p in ledger.get("params", []):
        if p["status"] == "conflict":
            values = " / ".join(f"{a['value']}@{a['source']['file']}:{a['source']['line']}" for a in p["alternatives"])
        else:
            values = p["raw"] or p["value"]
        src = p["sources"][0] if p.get("sources") else {}
        loc = f"{src.get('file','')}:{src.get('line','')}" if src else "—"
        lines.append(
            f"| `{p['name']}` | {values} | {p['unit'] or '—'} | {p['scope']} | {p['status']} | {loc} |"
        )
    lines += ["", f"共 **{len(ledger.get('params', []))}** 个参数；"
                  f"verified {sum(1 for p in ledger['params'] if p['status']=='verified')} / "
                  f"conflict {sum(1 for p in ledger['params'] if p['status']=='conflict')}。", ""]
    return "\n".join(lines)


def fact_source_map(ledger, datasets, controls):
    rows = []
    for p in ledger.get("params", []):
        for s in p.get("sources", []):
            rows.append({
                "kind": "param",
                "name": p["name"],
                "value": p["raw"] if p["status"] == "verified" else None,
                "status": p["status"],
                "source": {"file": s["file"], "line": s["line"], "quote": s["quote"]},
            })
    for did, d in (datasets or {}).items():
        for f, v in d.get("fields", {}).items():
            s = d.get("sources", {}).get(f, {})
            rows.append({"kind": "dataset", "name": f"{did}.{f}", "value": v, "status": "verified",
                         "source": {"file": s.get("file", ""), "line": s.get("line", 0), "quote": s.get("quote", "")}})
    for cid, c in (controls or {}).items():
        for f, v in c.get("fields", {}).items():
            s = c.get("sources", {}).get(f, {})
            rows.append({"kind": "control", "name": f"{cid}.{f}", "value": v, "status": "verified",
                         "source": {"file": s.get("file", ""), "line": s.get("line", 0), "quote": s.get("quote", "")}})
    return rows


def _pick(field, ctx):
    f = re.sub(r"[^a-z]", "", field.lower())
    if ("case" in f and "id" in f) or f == "id":
        return ctx["case_id"]
    if any(k in f for k in ("draft", "manuscript", "chapter", "section", "writing", "article", "text", "method")):
        return "draft.md"
    if any(k in f for k in ("source", "evidence", "provenance", "citation", "fact", "trace", "reference")):
        return ctx["fact_source_map"]
    if any(k in f for k in ("uncertain", "gap", "limit", "confirm", "question", "issue")):
        return ctx["gaps"]
    if any(k in f for k in ("change", "diff", "revision", "version")):
        return ctx["change_records"]
    if any(k in f for k in ("repro", "reproduc")):
        return "repro_checklist.md"
    if any(k in f for k in ("param", "ledger", "table")):
        return "param_table.md"
    if "audit" in f or "check" in f:
        return "audit.json"
    if "status" in f or "outcome" in f:
        return ctx["status"]
    if "coverage" in f:
        return ctx["coverage"]
    return None


def build_result(fields, ctx):
    result, unresolved = {"case_id": ctx["case_id"]}, []
    for f in fields:
        v = _pick(f, ctx)
        if v is None:
            result[f] = None
            unresolved.append(f)
        else:
            result[f] = v
    result["status"] = ctx["status"]
    result["artifacts"] = ctx["artifacts"]
    result["unresolved_contract_fields"] = unresolved
    result["fact_source_map"] = ctx["fact_source_map"]
    result["uncertainty"] = ctx["gaps"]
    result["change_records"] = ctx["change_records"]
    result["audit"] = ctx["audit_summary"]
    return result


def pack_check(root, max_files=50, max_bytes=500 * 1024, max_total=2 * 1024 * 1024):
    root = Path(root)
    issues, files, total = [], [], 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "__pycache__", ".venv", "venv")]
        for fn in filenames:
            p = Path(dirpath) / fn
            rel = p.relative_to(root).as_posix()
            files.append(rel)
            if p.is_symlink():
                issues.append(f"E_SYMLINK {rel}")
            if not p.suffix:
                issues.append(f"E_NO_SUFFIX {rel}")
            size = p.stat().st_size
            total += size
            if size > max_bytes:
                issues.append(f"E_FILE_TOO_BIG {rel} ({size}B)")
    if len(files) > max_files:
        issues.append(f"E_TOO_MANY_FILES {len(files)} > {max_files}")
    if total > max_total:
        issues.append(f"E_TOTAL_TOO_BIG {total} > {max_total}")
    return {"files": len(files), "bytes": total, "issues": issues, "ok": not issues}


def write_pack_report(path, report):
    write_json(path, report)
