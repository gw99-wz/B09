#!/usr/bin/env python3
"""CLI for the Methods & Experiments provenance kit.

Commands
  init   parse /input/case.json + materials, build the ledger, write a slot draft
  check  render the draft, run the numeric firewall, emit auditable deliverables
  all    init (if needed) + check

Exit codes
  0  ok            (may still be `partial`: gaps are reported, not hidden)
  2  hard failure  (E_UNBOUND_NUMBER / E_UNKNOWN_SLOT / E_MISSING_LIMITS ...)
  1  usage / IO error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pk import contract, coverage, emit, extract, firewall, gaps, ledger as ledger_mod, materials, render, repro
from pk.util import fmt_value, read_json, read_text, write_json, write_text


# --------------------------------------------------------------------------
# analysis
# --------------------------------------------------------------------------

def analyze(case_path, proposals_path=None):
    case_path = Path(case_path).resolve()
    case = contract.load_case(case_path)
    roots = contract.material_roots(case_path, case)
    index = materials.build_index(roots, exclude=(case_path,))
    cache = materials.load_lines(index)

    candidates = extract.extract_candidates(index)
    led = ledger_mod.build_ledger(candidates, cache)
    proposals = []
    if proposals_path and Path(proposals_path).exists():
        proposals = read_json(proposals_path)
    led = ledger_mod.apply_proposals(led, proposals, cache)

    ds = extract.extract_datasets(index)
    ct = extract.extract_controls(index)
    hints = extract.extract_version_hints(index)
    cmds = extract.extract_commands(index)

    datasets = {ds["id"]: ds} if ds else {}
    controls = {ct["id"]: ct} if ct else {}
    fields, shape, raw = contract.output_fields(case)
    return {
        "case_path": str(case_path),
        "case": case,
        "case_id": contract.case_id_of(case, case_path.parent.name),
        "fields": fields,
        "contract_shape": shape,
        "contract_raw": raw,
        "roots": [str(r) for r in roots],
        "index": index,
        "cache": cache,
        "ledger": led,
        "datasets": datasets,
        "controls": controls,
        "hints": hints,
        "commands": cmds,
    }


# --------------------------------------------------------------------------
# skeleton
# --------------------------------------------------------------------------

def _skeleton(a):
    led = a["ledger"]
    ds = a["datasets"].get("D1", {})
    ct = a["controls"].get("C1", {})
    rows = ["| 参数 | 取值 | 单位 | 作用对象 |", "|-|-|-|-|"]
    for p in led["params"]:
        if p["status"] == "conflict":
            continue
        rows.append(f"| `{p['name']}` | {{{{P:{p['id']}}}}} | {p['unit'] or '—'} | {p['scope']} |")

    lines = [
        "# Methods",
        "",
        "<!-- 自动骨架：所有取值都用 P 槽位，禁止手写数字。 -->",
        "",
        "## 1. Materials and Data",
        "",
        "本节说明数据来源、版本、规模、预处理、划分比例与随机方式。",
        "",
        f"- 数据集：{{{{D:D1}}}}" if ds else "- 数据集：[待确认:dataset]",
        "",
        "## 2. Method Steps",
        "",
        "1. **输入**：说明输入文件、数据子集与读取方式。",
        "2. **操作**：写清每一步的实际操作与所用脚本。",
        "3. **输出**：写清该步产生的文件或指标。",
        "4. **判断条件**：写清何时继续、何时停止或回退。",
        "",
        "## 3. Experimental Setup",
        "",
        "### 3.1 Hardware and Software",
        "",
        "说明硬件、Python / CUDA / 关键依赖版本。",
        "",
        "### 3.2 Training, Validation and Test Protocol",
        "",
        "分别说明训练、验证、测试流程，随机种子与重复次数。",
        "",
        "### 3.3 Parameters",
        "",
        "\n".join(rows),
        "",
        "## 4. Baselines and Controls",
        "",
        f"- 基线：{{{{C:C1}}}}" if ct else "- 基线：[待确认:baseline]",
        "",
        "## 5. Reproducibility",
        "",
        "代码版本、环境、数据获取方式与启动命令见复现清单。",
        "",
        "## 6. Limitations",
        "",
        "- 当 [具体失效场景] 时，[哪种结论] 不再成立；适用范围是 [边界]。",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def cmd_init(a, work):
    work = Path(work)
    (work / "pk").mkdir(parents=True, exist_ok=True)
    write_json(work / "pk" / "contract.json", {
        "case_id": a["case_id"], "shape": a["contract_shape"],
        "fields": a["fields"], "raw": a["contract_raw"],
    })
    write_json(work / "pk" / "materials.json", a["index"])
    write_json(work / "pk" / "ledger.json", a["ledger"])
    write_json(work / "pk" / "datasets.json", a["datasets"])
    write_json(work / "pk" / "controls.json", a["controls"])
    draft = work / "draft.src.md"
    if not draft.exists():
        write_text(draft, _skeleton(a))
    print(json.dumps({
        "stage": "init", "case_id": a["case_id"],
        "materials": len([m for m in a["index"] if m["kind"] not in ("binary", "noext")]),
        "params": len(a["ledger"]["params"]),
        "conflicts": len(a["ledger"]["conflicts"]),
        "datasets": list(a["datasets"]), "controls": list(a["controls"]),
        "draft": str(draft),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_check(a, work, out, draft_path, allow_path):
    work, out = Path(work), Path(out)
    draft_path = Path(draft_path) if draft_path else work / "draft.src.md"
    if not draft_path.exists():
        print(json.dumps({"error": f"draft not found: {draft_path}"}, ensure_ascii=False))
        return 1
    src = read_text(draft_path)

    r = render.render(src, a["ledger"], a["datasets"], a["controls"])
    allow = firewall.load_allowlist(allow_path)
    viol = firewall.check(r["rendered"], r["spans"], allow)
    lim = gaps.check_limitations(r["rendered"])

    rp = repro.build_repro(
        a["ledger"], a["datasets"].get("D1"), a["controls"].get("C1"),
        a["hints"], a["commands"], a["index"],
    )
    cv = coverage.build_coverage(
        a["ledger"], a["datasets"].get("D1"), a["controls"].get("C1"),
        a["hints"], r["rendered"], rp,
    )
    gp = gaps.build_gaps(cv, a["ledger"]["conflicts"], rp, r["queries"], lim)

    hard = [e for e in r["errors"]] + viol
    hard_codes = {"E_UNKNOWN_SLOT", "E_UNKNOWN_DATASET", "E_UNKNOWN_CONTROL", "E_BAD_SLOT", "E_CONFLICT_SLOT"}
    hard += [x for x in lim if x["code"] in ("E_MISSING_LIMITS", "E_EMPTY_LIMITS", "E_VAGUE_LIMIT")]
    failed = bool(viol) or any(e["code"] in hard_codes for e in r["errors"]) or any(
        x["code"] in ("E_MISSING_LIMITS", "E_EMPTY_LIMITS", "E_VAGUE_LIMIT") for x in lim
    )
    status = "failed" if failed else ("partial" if gp else "ok")

    fact = emit.fact_source_map(a["ledger"], a["datasets"], a["controls"])
    changes = [
        {"action": "extract", "detail": f"{len(a['ledger']['params'])} 参数候选，{len(a['ledger']['rejected'])} 条 locator 校验失败"},
        {"action": "render", "detail": f"{len(r['substitutions'])} 个槽位替换"},
        {"action": "firewall", "detail": f"{len(viol)} 个未绑定数值"},
        {"action": "gaps", "detail": f"{len(gp)} 条待确认"},
    ]
    audit = {
        "case_id": a["case_id"],
        "contract_shape": a["contract_shape"],
        "contract_fields": a["fields"],
        "render_errors": r["errors"],
        "unbound_numbers": viol,
        "limitation_issues": lim,
        "rejected_candidates": a["ledger"]["rejected"][:20],
        "proposals_rejected": a["ledger"].get("proposals_rejected", []),
        "substitutions": r["substitutions"],
        "coverage": cv["summary"],
        "repro": rp["summary"],
        "status": status,
        "draft_sha256_16": __import__("hashlib").sha256(src.encode()).hexdigest()[:16],
    }
    ctx = {
        "case_id": a["case_id"], "status": status,
        "fact_source_map": fact, "gaps": gp, "change_records": changes,
        "coverage": cv["summary"], "audit_summary": audit,
        "artifacts": {
            "draft": "draft.md", "param_table": "param_table.md",
            "repro": "repro_checklist.md", "queries": "author_queries.md",
            "gaps": "gaps.json", "ledger": "ledger.json", "audit": "audit.json",
        },
    }
    result = emit.build_result(a["fields"], ctx)

    out.mkdir(parents=True, exist_ok=True)
    if failed:
        write_text(out / "draft.rejected.md", r["rendered"])
    else:
        write_text(out / "draft.md", r["rendered"])
    write_text(out / "param_table.md", emit.param_table_md(a["ledger"]))
    write_text(out / "repro_checklist.md", repro.render_md(rp))
    write_text(out / "author_queries.md", gaps.render_queries_md(gp))
    write_json(out / "gaps.json", gp)
    write_json(out / "ledger.json", a["ledger"])
    write_json(out / "coverage.json", cv)
    write_json(out / "limitations.json", lim)
    write_json(out / "fact_source_map.json", fact)
    write_json(out / "audit.json", audit)
    write_json(out / "result.json", result)

    pack = emit.pack_check(out)
    write_json(out / "pack_report.json", pack)
    print(json.dumps({
        "stage": "check", "case_id": a["case_id"], "status": status,
        "unbound_numbers": len(viol), "render_errors": len(r["errors"]),
        "limitation_issues": len(lim), "gaps": len(gp),
        "coverage": cv["summary"], "coverage_score": cv["score"],
        "repro": rp["summary"], "repro_score": rp["score"],
        "pack": pack, "out": str(out),
    }, ensure_ascii=False, indent=2))
    return 2 if failed else 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="pk")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("--case", required=True)
    p_init.add_argument("--work", default="work")
    p_init.add_argument("--proposals", default=None)

    p_chk = sub.add_parser("check")
    p_chk.add_argument("--case", required=True)
    p_chk.add_argument("--work", default="work")
    p_chk.add_argument("--out", default="output")
    p_chk.add_argument("--draft", default=None)
    p_chk.add_argument("--allow", default=None)
    p_chk.add_argument("--proposals", default=None)

    p_all = sub.add_parser("all")
    p_all.add_argument("--case", required=True)
    p_all.add_argument("--work", default="work")
    p_all.add_argument("--out", default="output")
    p_all.add_argument("--proposals", default=None)
    p_all.add_argument("--allow", default=None)

    args = ap.parse_args(argv)
    case = Path(args.case)
    if case.is_dir():
        case = case / "case.json"
    try:
        a = analyze(case, getattr(args, "proposals", None))
        if args.cmd == "init":
            return cmd_init(a, args.work)
        if args.cmd == "check":
            return cmd_check(a, args.work, args.out, args.draft, args.allow)
        if args.cmd == "all":
            cmd_init(a, args.work)
            return cmd_check(a, args.work, args.out, None, args.allow)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
