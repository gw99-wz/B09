"""Ledger: group candidates, verify against the raw locator, never pick a winner.

Rules enforced here
  1. A candidate is accepted only if its quoted text really occurs at its locator.
  2. Same key + same canonical value  -> one `verified` parameter (all sources kept).
  3. Same key + different values      -> `conflict`; every alternative kept and
     surfaced to the author.  The ledger never silently chooses one.
  4. Values proposed by the model are accepted only through `apply_proposals`,
     which re-reads the locator and byte-compares the quote.
"""

from __future__ import annotations

import re
from pathlib import Path

from .util import canon_number, norm_key, read_text, slug

ALIASES = {
    "lr": "learning_rate",
    "bs": "batch_size",
    "wd": "weight_decay",
}


def canonical_name(key: str) -> str:
    key = norm_key(key)
    parts = key.split("_")
    for i in range(len(parts)):
        if parts[i] in ALIASES:
            parts[i] = ALIASES[parts[i]]
    return "_".join(parts)


def infer_scope(key: str) -> str:
    k = key.lower()
    if re.search(r"(^|_)val(_|$)", k):
        return "validation"
    if re.search(r"(^|_)test(_|$)", k):
        return "test"
    if re.search(r"(^|_)train(_|$)", k):
        return "train"
    if re.search(r"(^|_)eval(_|$)", k):
        return "eval"
    return "all"


def _line_text(cache, source):
    lines = cache.get(source["file"])
    if lines is None:
        return None
    ln = int(source.get("line", 0))
    if ln < 1 or ln > len(lines):
        return None
    return lines[ln - 1]


def verify_source(source, cache) -> bool:
    line = _line_text(cache, source)
    if line is None:
        return False
    quote = (source.get("quote") or "").strip()
    if not quote:
        return False
    return quote in line or line.strip() in quote


def build_ledger(candidates, cache):
    rejected = []
    accepted = []
    for c in candidates:
        if verify_source(c["source"], cache):
            accepted.append(c)
        else:
            rejected.append({**c, "code": "E_LEDGER_MISMATCH"})

    groups = {}
    for c in accepted:
        name = canonical_name(c["key"])
        groups.setdefault(name, []).append(c)

    params, conflicts = [], []
    for idx, name in enumerate(sorted(groups), 1):
        items = groups[name]
        values = sorted({i["value"] for i in items})
        items.sort(key=lambda x: (-x["priority"], x["source"]["file"], x["source"]["line"]))
        sources = []
        seen = set()
        for i in items:
            k = (i["source"]["file"], i["source"]["line"])
            if k in seen:
                continue
            seen.add(k)
            sources.append({**i["source"], "extractor": i["extractor"]})
        pid = f"P_{slug(name)}"
        if len(values) == 1:
            primary = items[0]
            params.append({
                "id": pid,
                "name": name,
                "value": primary["value"],
                "raw": primary["raw"],
                "unit": primary["unit"],
                "kind": primary["kind"],
                "scope": infer_scope(name),
                "status": "verified",
                "sources": sources,
                "alternatives": [],
                "extractor": primary["extractor"],
            })
        else:
            alternatives = []
            for v in values:
                pick = next(i for i in items if i["value"] == v)
                alternatives.append({
                    "value": v,
                    "raw": pick["raw"],
                    "unit": pick["unit"],
                    "source": pick["source"],
                })
            params.append({
                "id": pid,
                "name": name,
                "value": None,
                "raw": None,
                "unit": items[0]["unit"],
                "kind": items[0]["kind"],
                "scope": infer_scope(name),
                "status": "conflict",
                "sources": sources,
                "alternatives": alternatives,
            })
            conflicts.append({
                "param_id": pid,
                "name": name,
                "values": values,
                "alternatives": alternatives,
            })
    return {"params": params, "conflicts": conflicts, "rejected": rejected}


def apply_proposals(ledger, proposals, cache):
    """Merge model-proposed values only after locator + quote verification."""
    params = {p["name"]: p for p in ledger["params"]}
    accepted, rejected = [], []
    for prop in proposals or []:
        name = canonical_name(prop.get("key") or prop.get("name") or "")
        src = prop.get("source") or prop.get("locator") or {}
        if isinstance(src, str):
            m = re.match(r"^(.*?):(\d+)$", src.strip())
            src = {"file": m.group(1), "line": int(m.group(2)), "quote": ""} if m else {}
        quote = (prop.get("quote") or src.get("quote") or "").strip()
        if quote:
            src["quote"] = quote
        src.setdefault("file", "")
        src.setdefault("line", 0)
        if not name or not src.get("file") or not quote:
            rejected.append({**prop, "code": "E_PROPOSAL_INCOMPLETE"})
            continue
        if not verify_source(src, cache):
            rejected.append({**prop, "code": "E_PROPOSAL_QUOTE_NOT_FOUND"})
            continue
        want = canon_number(prop.get("value")) or str(prop.get("value", "")).strip()
        got = canon_number(prop.get("value"))
        line = _line_text(cache, src) or ""
        if got is not None:
            nums = re.findall(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", line)
            canon_nums = {canon_number(n) for n in nums}
            if got not in canon_nums:
                rejected.append({**prop, "code": "E_PROPOSAL_VALUE_MISMATCH"})
                continue
        if name in params:
            p = params[name]
            if p["status"] == "verified" and p["value"] != want:
                rejected.append({**prop, "code": "E_PROPOSAL_CONTRADICTS_LEDGER"})
                continue
            p["sources"].append({**src, "extractor": "model"})
            continue
        params[name] = {
            "id": f"P_{slug(name)}",
            "name": name,
            "value": want,
            "raw": str(prop.get("value")),
            "unit": prop.get("unit", ""),
            "kind": "number" if got is not None else "string",
            "scope": infer_scope(name),
            "status": "verified",
            "sources": [{**src, "extractor": "model"}],
            "alternatives": [],
            "extractor": "model",
        }
        accepted.append(name)
    ledger["params"] = sorted(params.values(), key=lambda p: p["name"])
    ledger["proposals_accepted"] = accepted
    ledger["proposals_rejected"] = rejected
    return ledger


def param_map(ledger):
    return {p["id"]: p for p in ledger["params"]}


def param_by_name(ledger):
    return {p["name"]: p for p in ledger["params"]}
