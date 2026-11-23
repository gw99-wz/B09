"""Gap register + limitation auditor: the mechanical answer to "说得住".

A gap is never dropped: it must end up either as a `{{?key}}` marker in the
draft or as a line in `author_queries.md`.
"""

from __future__ import annotations

import re

BANNED = [
    "受限于时间", "受限于实验条件", "由于时间关系", "未来工作", "有待进一步研究",
    "尚需进一步研究", "具有一定的局限性", "存在一定的局限", "广泛适用",
    "受限于数据", "由于数据有限", "受限于篇幅",
]

SECTION_RE = re.compile(r"^#{1,6}\s*(?:[0-9.]+\s*)?(?:Limitations?|局限|限制)\s*$", re.I)
SCENARIO_HINT = re.compile(
    r"(当|如果|若|一旦|在.{0,20}(?:情况|场景|条件|分布|规模)下|"
    r"if|when|scenario|fails?|degrades?|breaks?|only valid|not applicable)",
    re.I,
)


def _limitations_section(text):
    lines = text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if SECTION_RE.match(ln.strip()):
            start = i + 1
            break
    if start is None:
        return None
    body = []
    for ln in lines[start:]:
        if re.match(r"^#{1,6}\s", ln):
            break
        body.append(ln)
    return "\n".join(body)


def check_limitations(text):
    issues = []
    body = _limitations_section(text)
    if body is None:
        return [{"code": "E_MISSING_LIMITS", "detail": "缺少 Limitations / 限制 小节"}]
    if not body.strip():
        return [{"code": "E_EMPTY_LIMITS", "detail": "Limitations 小节为空"}]
    for phrase in BANNED:
        if phrase in body:
            issues.append({"code": "E_VAGUE_LIMIT", "token": phrase, "detail": "命中套话词表"})
    bullets = [ln.strip() for ln in body.splitlines() if re.match(r"^\s*(?:[-*]|\d+[.)])\s+\S", ln)]
    for b in bullets:
        content = re.sub(r"^\s*(?:[-*]|\d+[.)])\s+", "", b)
        if len(content) < 18:
            issues.append({"code": "E_SHALLOW_LIMIT", "token": content[:40], "detail": "限制条目过短，缺少具体失效场景"})
        elif not SCENARIO_HINT.search(content):
            issues.append({"code": "E_NO_SCENARIO", "token": content[:60], "detail": "限制条目未指向具体失效场景"})
    return issues


def build_gaps(coverage, conflicts, repro, queries, limit_issues):
    gaps = []
    seen = set()

    def add(element, what, why, impact, question):
        if element in seen:
            return
        seen.add(element)
        gaps.append({
            "id": f"G{len(gaps) + 1:02d}",
            "element": element,
            "what": what,
            "why": why,
            "impact": impact,
            "question": question,
            "status": "open",
        })

    for cls, fields in coverage.get("classes", {}).items():
        for f, v in fields.items():
            if v["status"] == "present":
                continue
            if v["status"] == "conflict":
                continue
            if cls == "params" and f in ("unit", "scope") and v["status"] == "partial":
                continue
            add(
                f"{cls}.{f}",
                f"{cls}.{f} 不足（{v['status']}）",
                v.get("detail") or "材料中未找到可核对来源",
                "章节可能缺少该要素或无法复现",
                f"请作者补充/确认 {cls}.{f} 的取值与来源",
            )

    for c in conflicts:
        add(
            f"params.{c['name']}",
            f"参数冲突：{c['name']} 有 {len(c['values'])} 个取值",
            "材料间不一致：" + "; ".join(
                f"{a['value']} @ {a['source']['file']}:{a['source']['line']}" for a in c["alternatives"]
            ),
            "无法确定正文该写哪个值，写错会破坏可复现性",
            f"请作者确认 {c['name']} 以哪份材料为准",
        )

    for it in repro.get("items", []):
        if it["status"] in ("present",):
            continue
        if it.get("ask"):
            add(f"repro.{it['id']}", f"复现项缺失：{it['id']}", it["value"], "读者无法按章节复做", it["ask"])

    for q in queries or []:
        add(f"draft.{q['key']}", f"正文待确认：{q['key']}", q.get("reason", ""), "该处结论暂时不成立", f"请确认 {q['key']}")

    for iss in limit_issues or []:
        add("limitations", iss["detail"], iss.get("token", ""), "限制条件不可信", "请把限制改写成具体失效场景")

    return gaps


def render_queries_md(gaps, coverage=None):
    lines = ["# 作者确认清单（Author Queries）", "",
             "> 每条缺口都必须有去向；未确认前不得在正文中补造数值或结论。", ""]
    if not gaps:
        lines.append("无待确认项。")
        return "\n".join(lines) + "\n"
    lines += ["| # | 要素 | 缺口 | 依据 | 影响 | 需要作者回答 |", "|-|-|-|-|-|-|"]
    for g in gaps:
        lines.append(
            f"| {g['id']} | {g['element']} | {g['what']} | {g['why']} | {g['impact']} | {g['question']} |"
        )
    lines += ["", f"共 **{len(gaps)}** 条待确认。", ""]
    return "\n".join(lines)
