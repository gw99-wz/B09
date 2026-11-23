"""Reproduction checklist generator: the mechanical answer to "做得着".

Every item is derived from materials / ledger; missing items are printed as
[MISSING] instead of being dropped.
"""

from __future__ import annotations

import re

ITEM_LABELS = {
    "code_version": "代码版本",
    "environment": "运行环境",
    "dependencies": "依赖安装",
    "data": "数据获取",
    "seeds": "随机种子",
    "repeats": "重复次数",
    "commands": "运行命令",
    "expected_output": "预期产物",
}


def _find_param(ledger, pattern):
    for p in ledger.get("params", []):
        if p.get("status") == "verified" and re.search(pattern, p["name"]):
            return p
    return None


def build_repro(ledger, datasets, controls, hints, commands, index):
    items = []

    commit = hints.get("commit", {}).get("value")
    if commit:
        items.append({"id": "code_version", "status": "present", "value": commit,
                      "source": hints["commit"].get("file", "")})
    else:
        items.append({"id": "code_version", "status": "missing", "value": "[MISSING] commit / release",
                      "source": "", "ask": "请作者提供代码仓库 commit 或 release 版本号"})

    py = hints.get("python", {}).get("value")
    cuda = hints.get("cuda", {}).get("value")
    torch = hints.get("torch", {}).get("value")
    hw = hints.get("hardware", {}).get("value")
    bits = []
    if hw:
        bits.append(f"GPU {hw}")
    if py:
        bits.append(f"Python {py}")
    if torch:
        bits.append(f"torch {torch}")
    if cuda:
        bits.append(f"CUDA {cuda}")
    items.append({
        "id": "environment",
        "status": "present" if bits else "missing",
        "value": "; ".join(bits) if bits else "[MISSING] OS / Python / CUDA",
        "source": "log" if bits else "",
        "ask": "" if bits else "请作者提供 Python / CUDA / OS 版本",
    })

    req = [m for m in index if m["file"].lower().endswith(("requirements.txt", "environment.yml", "environment.yaml"))]
    items.append({
        "id": "dependencies",
        "status": "present" if req else "inferred",
        "value": "pip install -r requirements.txt" if req else "[MISSING] requirements.txt",
        "source": req[0]["file"] if req else "",
    })

    ds = (datasets or {}).get("fields", {})
    if ds.get("name") and ds.get("version"):
        value = f"{ds['name']} {ds['version']}"
        if ds.get("split"):
            value += f"; {ds['split']}"
        items.append({"id": "data", "status": "present", "value": value, "source": "dataset note"})
    elif ds.get("name"):
        items.append({"id": "data", "status": "partial", "value": f"{ds['name']} (版本缺失)",
                      "source": "dataset note", "ask": "请作者确认数据集版本与获取方式"})
    else:
        items.append({"id": "data", "status": "missing", "value": "[MISSING] dataset name/version",
                      "source": "", "ask": "请作者提供数据集名称、版本与获取方式"})

    seed_p = _find_param(ledger, r"^(train_)?seed$")
    items.append({
        "id": "seeds", "status": "present" if seed_p else "missing",
        "value": f"{seed_p['name']} = {seed_p['raw']}" if seed_p else "[MISSING] random seed",
        "source": seed_p["sources"][0]["file"] if seed_p and seed_p.get("sources") else "",
        "ask": "" if seed_p else "请作者提供训练/划分随机种子",
    })

    ct = (controls or {}).get("fields", {})
    items.append({
        "id": "repeats", "status": "present" if ct.get("stat") else "partial",
        "value": ct.get("stat", "[MISSING] 重复次数"),
        "source": "control note" if ct.get("stat") else "",
        "ask": "" if ct.get("stat") else "请作者确认每个设置重复几次",
    })

    if commands:
        items.append({"id": "commands", "status": "present", "value": commands[0]["cmd"],
                      "source": commands[0]["source"]["file"]})
    else:
        items.append({"id": "commands", "status": "missing", "value": "[MISSING] 启动命令",
                      "source": "", "ask": "请作者提供实际运行命令（含配置与种子参数）"})

    out_p = _find_param(ledger, r"(output|save|ckpt|checkpoint)")
    items.append({
        "id": "expected_output", "status": "present" if out_p else "inferred",
        "value": out_p["raw"] if out_p else "预期产物：日志 + 指标 + 模型权重",
        "source": out_p["sources"][0]["file"] if out_p and out_p.get("sources") else "",
    })

    present = sum(1 for i in items if i["status"] == "present")
    partial = sum(1 for i in items if i["status"] == "partial")
    total = len(items)
    return {
        "items": items,
        "summary": {"present": present, "partial": partial, "missing": total - present - partial, "total": total},
        "score": round((present + 0.5 * partial) / total, 4) if total else 0.0,
    }


def render_md(repro):
    lines = [
        "# 复现清单（Reproduction Checklist）",
        "",
        "> 由参数台账与材料确定性生成；`[MISSING]` 表示材料不足，需作者确认，不是笔误。",
        "",
        "| 项 | 内容 | 状态 | 来源 |",
        "|-|-|-|-|",
    ]
    for it in repro.get("items", []):
        label = ITEM_LABELS.get(it["id"], it["id"])
        src = it.get("source") or "—"
        lines.append(f"| {label} | {it['value']} | {it['status']} | {src} |")
    s = repro["summary"]
    lines += [
        "",
        f"**覆盖率（present + 0.5×partial）/ total = {repro['score']:.2f}**"
        f"（present {s['present']} / partial {s['partial']} / missing {s['missing']} / total {s['total']}）",
        "",
    ]
    asks = [it for it in repro.get("items", []) if it.get("ask")]
    if asks:
        lines.append("## 需作者补充")
        lines.append("")
        for it in asks:
            lines.append(f"- `{it['id']}`：{it['ask']}")
        lines.append("")
    return "\n".join(lines)
