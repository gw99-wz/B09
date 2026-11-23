"""Slot renderer.

The model writes prose that references ledger ids; this module is the *only*
place where a number becomes visible text.  Every substitution is recorded as
a span so the firewall can tell "came from the ledger" from "typed by hand".
"""

from __future__ import annotations

import re

from .ledger import param_by_name, param_map

SLOT_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")


def _descriptor(fields: dict) -> str:
    name = fields.get("name") or fields.get("baseline") or ""
    ver = fields.get("version") or fields.get("baseline_version") or ""
    bits = [str(name)]
    if ver:
        v = str(ver)
        bits.append(f"v{v}" if v.replace(".", "").isdigit() else v)
    return " ".join(b for b in bits if b)


def render(text: str, ledger: dict, datasets=None, controls=None):
    params = param_map(ledger)
    by_name = param_by_name(ledger)
    datasets = datasets or {}
    controls = controls or {}
    out, spans, errors, queries, subs = [], [], [], [], []
    last = 0
    for m in SLOT_RE.finditer(text):
        out.append(text[last:m.start()])
        pos = sum(len(x) for x in out)
        body = m.group(1).strip()
        rendered = None
        kind, sid = body, body

        if body.startswith("?"):
            key = body[1:].strip() or "unknown"
            rendered = f"[待确认:{key}]"
            queries.append({"key": key, "reason": "draft 标记待确认", "code": "Q_TODO"})
            kind, sid = "todo", key
        elif body.startswith("P:"):
            ref = body[2:].strip()
            pid, _, attr = ref.partition(".")
            p = params.get(pid) or by_name.get(pid)
            if not p:
                errors.append({"code": "E_UNKNOWN_SLOT", "slot": body, "line": text.count("\n", 0, m.start()) + 1})
                rendered = f"[未解析:{pid}]"
            elif p["status"] == "conflict":
                errors.append({"code": "E_CONFLICT_SLOT", "slot": body, "param_id": pid})
                rendered = f"[冲突:{pid}]"
            else:
                attr = attr or "value"
                if attr == "raw":
                    rendered = p["raw"] or ""
                elif attr == "unit":
                    rendered = p["unit"] or ""
                elif attr == "name":
                    rendered = p["name"]
                else:
                    rendered = p["raw"] if p["kind"] != "number" else (p["raw"] or p["value"])
                    if p["unit"] and p["unit"] not in ("1", "dimensionless"):
                        rendered = f"{rendered} {p['unit']}".strip()
            kind, sid = "param", p["id"] if p else pid
        elif body.startswith("D:"):
            did = body[2:].strip()
            d = datasets.get(did)
            if not d:
                errors.append({"code": "E_UNKNOWN_DATASET", "slot": body})
                rendered = f"[未解析:{did}]"
            else:
                rendered = _descriptor(d.get("fields", {}))
            kind, sid = "dataset", did
        elif body.startswith("C:"):
            cid = body[2:].strip()
            c = controls.get(cid)
            if not c:
                errors.append({"code": "E_UNKNOWN_CONTROL", "slot": body})
                rendered = f"[未解析:{cid}]"
            else:
                rendered = _descriptor(c.get("fields", {}))
            kind, sid = "control", cid
        else:
            errors.append({"code": "E_BAD_SLOT", "slot": body})
            rendered = f"[坏槽位:{body}]"

        if rendered is None:
            rendered = ""
        out.append(rendered)
        spans.append((pos, pos + len(rendered), kind, sid))
        subs.append({"slot": body, "rendered": rendered, "kind": kind, "id": sid})
        last = m.end()
    out.append(text[last:])
    return {
        "rendered": "".join(out),
        "spans": spans,
        "errors": errors,
        "queries": queries,
        "substitutions": subs,
    }
