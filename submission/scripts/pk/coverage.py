"""Six-class coverage matrix: this is the mechanical answer to "写得全"."""

from __future__ import annotations

import re

REQUIRED = {
    "steps": ["input", "operation", "output", "decision"],
    "settings": ["hardware", "software", "environment", "seed", "repeats", "split"],
    "params": ["name", "value", "unit", "scope", "source"],
    "datasets": ["name", "version", "size", "preprocess", "split", "random"],
    "controls": ["baseline", "version", "budget", "metric", "stat"],
    "repro": ["code_version", "environment", "command", "data_access"],
}

DATASET_KEYS = {
    "name": "name", "version": "version", "size": "size",
    "preprocess": "preprocess", "split": "split", "random": "split_seed",
}
CONTROL_KEYS = {
    "baseline": "baseline", "version": "baseline_version", "budget": "budget",
    "metric": "metric", "stat": "stat",
}


def _param_names(ledger):
    return [p["name"] for p in ledger.get("params", [])]


def _has_param(ledger, pattern):
    return any(re.search(pattern, n) for n in _param_names(ledger))


def _draft_steps(draft_text):
    n = 0
    for ln in draft_text.splitlines():
        if re.match(r"^\s*\d+[.)]\s+\S", ln):
            n += 1
    return n


def build_coverage(ledger, datasets, controls, hints, draft_text, repro):
    out = {}
    params = ledger.get("params", [])
    verified = [p for p in params if p.get("status") == "verified"]
    conflicts = [p for p in params if p.get("status") == "conflict"]

    # --- params -----------------------------------------------------------
    out["params"] = {
        "name": {"status": "present" if params else "missing", "detail": f"{len(params)} 个参数"},
        "value": {"status": "present" if verified else ("conflict" if conflicts else "missing")},
        "unit": {"status": "present" if any(p.get("unit") for p in verified) else "missing"},
        "scope": {"status": "present" if any(p.get("scope") != "all" for p in verified) else "partial"},
        "source": {"status": "present" if verified and all(p.get("sources") for p in verified) else "missing"},
    }

    # --- datasets ---------------------------------------------------------
    ds = (datasets or {}).get("fields", {})
    out["datasets"] = {
        k: {"status": "present" if ds.get(v) else ("partial" if k == "random" and ds.get("split") else "missing"),
            "detail": ds.get(v, "")}
        for k, v in DATASET_KEYS.items()
    }

    # --- controls ---------------------------------------------------------
    ct = (controls or {}).get("fields", {})
    out["controls"] = {
        k: {"status": "present" if ct.get(v) else "missing", "detail": ct.get(v, "")}
        for k, v in CONTROL_KEYS.items()
    }

    # --- settings ---------------------------------------------------------
    env_bits = [hints.get("python", {}).get("value"), hints.get("cuda", {}).get("value")]
    env_bits = [b for b in env_bits if b]
    out["settings"] = {
        "hardware": {"status": "present" if hints.get("hardware") else "missing",
                     "detail": hints.get("hardware", {}).get("value", "")},
        "software": {"status": "present" if env_bits else "missing", "detail": " / ".join(env_bits)},
        "environment": {"status": "present" if hints.get("cuda") or hints.get("torch") else "partial"},
        "seed": {"status": "present" if _has_param(ledger, r"^(train_)?seed$") else "missing"},
        "repeats": {"status": "present" if (ct.get("stat") or _has_param(ledger, r"repeat")) else "missing"},
        "split": {"status": "present" if ds.get("split") else "missing"},
    }

    # --- steps ------------------------------------------------------------
    n = _draft_steps(draft_text)
    out["steps"] = {
        "input": {"status": "present" if n else "missing", "detail": f"{n} 条编号步骤"},
        "operation": {"status": "present" if n else "missing"},
        "output": {"status": "present" if n else "missing"},
        "decision": {"status": "present" if n else "missing"},
    }

    # --- repro ------------------------------------------------------------
    out["repro"] = {}
    repro_by_id = {i["id"]: i for i in (repro or {}).get("items", [])}
    mapping = {
        "code_version": "code_version", "environment": "environment",
        "command": "commands", "data_access": "data",
    }
    for k, rid in mapping.items():
        item = repro_by_id.get(rid, {})
        out["repro"][k] = {"status": item.get("status", "missing"), "detail": item.get("value", "")}

    flat, present, partial = {}, 0, 0
    for cls, fields in out.items():
        for f, v in fields.items():
            flat[f"{cls}.{f}"] = v
            if v["status"] == "present":
                present += 1
            elif v["status"] in ("partial", "conflict"):
                partial += 1
    total = len(flat)
    return {
        "classes": out,
        "flat": flat,
        "summary": {"present": present, "partial": partial, "missing": total - present - partial, "total": total},
        "score": round((present + 0.5 * partial) / total, 4) if total else 0.0,
    }
