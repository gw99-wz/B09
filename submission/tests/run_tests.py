#!/usr/bin/env python3
"""Regression suite.  Every test maps to one real failure mode of base agents.

Run:  python submission/tests/run_tests.py
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import secrets
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run as pkrun  # noqa: E402
from pk import emit  # noqa: E402

CONFIG = """train:
  batch_size: 64
  learning_rate: 0.001
  seed: 42
"""
LOG = """seed=42
batch_size=64
python=3.11.9
"""
DATASET = """Dataset: TinySet
Version: v1
Size: 100 images
Split: train 80 / val 10 / test 10
Split seed: 42
"""
NOTES = """Baseline: MLP
Baseline version: 1.0
Budget: same
Metric: accuracy
Stat: 3 repeats
"""

DRAFT = """# Methods

## 1. Materials and Data

Use {{D:D1}}.

## 2. Method Steps

1. 输入：读取数据。
2. 操作：按配置训练。
3. 输出：写出检查点。
4. 判断条件：指标不升则停止。

## 3. Experimental Setup

### 3.1 Hardware and Software

Python {{P:python}}.

### 3.2 Training, Validation and Test Protocol

Batch size {{P:train_batch_size}}; seed {{P:train_seed}}.

## 4. Baselines and Controls

Baseline {{C:C1}}.

## 5. Reproducibility

See checklist.

## 6. Limitations

- 当批大小 {{P:train_batch_size}} 超出显存时训练会 OOM；适用范围为单卡。
"""


class Case:
    def __init__(self, files=None, draft=DRAFT, contract=None, proposals=None, case_extra=None):
        base = Path(os.environ.get("PK_TEST_TMP") or (ROOT.parent / ".tmp"))
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = base / f"pk-test-{secrets.token_hex(6)}"
        self.tmp.mkdir()
        files = dict(files or {})
        files.setdefault("materials/config.yaml", CONFIG)
        files.setdefault("materials/train.log", LOG)
        files.setdefault("materials/dataset.md", DATASET)
        files.setdefault("materials/paper_notes.md", NOTES)
        for rel, content in files.items():
            p = self.tmp / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8", newline="\n")
        case = {"case_id": "test-case", "materials": ["materials"],
                "output_contract": contract or ["draft_md", "fact_source_map", "status"]}
        case.update(case_extra or {})
        self.case_path = self.tmp / "case.json"
        self.case_path.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
        self.draft_path = self.tmp / "draft.src.md"
        self.draft_path.write_text(draft, encoding="utf-8", newline="\n")
        self.proposals_path = None
        if proposals is not None:
            self.proposals_path = self.tmp / "proposals.json"
            self.proposals_path.write_text(json.dumps(proposals), encoding="utf-8")
        self.out = self.tmp / "out"

    def run(self):
        a = pkrun.analyze(self.case_path, self.proposals_path)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = pkrun.cmd_check(a, self.tmp / "work", self.out, self.draft_path, None)
        return code, json.loads(buf.getvalue()), a

    def read(self, name):
        p = self.out / name
        return p.read_text(encoding="utf-8") if p.exists() else None

    def close(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


def _check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def test_baseline_passes():
    c = Case()
    try:
        code, summary, _ = c.run()
        _check(code == 0, f"exit {code}")
        _check(summary["unbound_numbers"] == 0, "unexpected unbound")
        _check(summary["render_errors"] == 0, "unexpected render error")
        _check(c.read("draft.md") is not None, "draft.md missing")
        _check(c.read("draft.rejected.md") is None, "rejected draft leaked")
    finally:
        c.close()


def test_unbound_number_is_blocked():
    draft = DRAFT.replace("Batch size {{P:train_batch_size}}", "Batch size 32")
    c = Case(draft=draft)
    try:
        code, summary, _ = c.run()
        _check(code == 2, f"expected hard failure, got {code}")
        _check(summary["unbound_numbers"] >= 1, "firewall did not fire")
        _check(summary["status"] == "failed", "status not failed")
        audit = json.loads(c.read("audit.json"))
        _check(any(v["token"] == "32" for v in audit["unbound_numbers"]), "token 32 not reported")
        _check(c.read("draft.md") is None, "draft.md must not be emitted on failure")
        _check(c.read("draft.rejected.md") is not None, "rejected draft missing")
    finally:
        c.close()


def test_conflict_not_resolved():
    files = {"materials/config.yaml": "learning_rate: 0.1\n", "materials/train.log": "learning_rate=0.01\n"}
    draft = DRAFT.replace("Batch size {{P:train_batch_size}}", "LR {{P:learning_rate}}")
    c = Case(files=files, draft=draft)
    try:
        code, summary, a = c.run()
        _check(code == 2, f"expected hard failure, got {code}")
        names = [x["name"] for x in a["ledger"]["conflicts"]]
        _check("learning_rate" in names, f"conflict missing: {names}")
        audit = json.loads(c.read("audit.json"))
        _check(any(e["code"] == "E_CONFLICT_SLOT" for e in audit["render_errors"]), "conflict slot not blocked")
    finally:
        c.close()


def test_missing_seed_becomes_gap():
    files = {"materials/config.yaml": "train:\n  batch_size: 64\n", "materials/train.log": "batch_size=64\npython=3.11.9\n"}
    draft = DRAFT.replace("; seed {{P:train_seed}}", "")
    c = Case(files=files, draft=draft)
    try:
        code, summary, _ = c.run()
        _check(code == 0, f"exit {code}")
        gaps = json.loads(c.read("gaps.json"))
        _check(any(g["element"] == "settings.seed" for g in gaps), "seed gap missing")
        repro = c.read("repro_checklist.md")
        _check("[MISSING] random seed" in repro, "repro seed missing marker absent")
    finally:
        c.close()


def test_vague_limitation_blocked():
    draft = DRAFT.replace(
        "- 当批大小 {{P:train_batch_size}} 超出显存时训练会 OOM；适用范围为单卡。",
        "- 受限于时间，我们只完成了部分实验。",
    )
    c = Case(draft=draft)
    try:
        code, summary, _ = c.run()
        _check(code == 2, f"expected hard failure, got {code}")
        audit = json.loads(c.read("audit.json"))
        _check(any(e["code"] == "E_VAGUE_LIMIT" for e in audit["limitation_issues"]), "vague limit not caught")
    finally:
        c.close()


def test_unknown_slot_blocked():
    c = Case(draft=DRAFT + "\n额外：{{P:does_not_exist}}\n")
    try:
        code, summary, _ = c.run()
        _check(code == 2, f"expected hard failure, got {code}")
        audit = json.loads(c.read("audit.json"))
        _check(any(e["code"] == "E_UNKNOWN_SLOT" for e in audit["render_errors"]), "unknown slot not caught")
    finally:
        c.close()


def test_forged_proposal_rejected():
    proposals = [{
        "key": "learning_rate", "value": "0.5",
        "locator": {"file": "materials/config.yaml", "line": 3, "quote": "learning_rate: 0.001"},
    }]
    c = Case(proposals=proposals)
    try:
        code, _, a = c.run()
        rej = a["ledger"].get("proposals_rejected", [])
        _check(any(r["code"] in ("E_PROPOSAL_VALUE_MISMATCH", "E_PROPOSAL_QUOTE_NOT_FOUND") for r in rej),
               f"proposal not rejected: {rej}")
        _check(a["ledger"].get("proposals_accepted", []) == [], "forged proposal accepted")
    finally:
        c.close()


def test_contract_unresolved_field():
    c = Case(contract=["draft_md", "mystery_field"])
    try:
        c.run()
        result = json.loads(c.read("result.json"))
        _check(result["mystery_field"] is None, "unknown field should be null")
        _check("mystery_field" in result["unresolved_contract_fields"], "unresolved not recorded")
    finally:
        c.close()


def test_idempotent():
    c = Case()
    try:
        c.run()
        first = c.read("draft.md")
        c.run()
        second = c.read("draft.md")
        _check(first is not None and first == second, "draft not idempotent")
    finally:
        c.close()


def test_pack_is_clean():
    report = emit.pack_check(ROOT)
    _check(report["ok"], f"pack issues: {report['issues']}")


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed, failed = 0, []
    for fn in tests:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
            passed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL  {fn.__name__}: {exc}")
            failed.append((fn.__name__, str(exc)))
    print(f"\n{passed}/{len(tests)} passed")
    if failed:
        for name, err in failed:
            print(f"  - {name}: {err}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
