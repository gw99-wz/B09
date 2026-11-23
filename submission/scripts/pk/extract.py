"""Deterministic candidate extraction from configs / logs / code / docs.

The extractors never decide truth: they only propose
    {key, raw, value, unit, source:{file,line,quote}, extractor, priority}
and the ledger layer verifies them by re-reading the locator.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from .util import canon_number, norm_key, read_text, sha256_text, split_value_unit, to_bool
from .yamlmini import parse_scalars

SCALAR_KEYS_SKIP = {
    "epoch", "step", "iter", "iteration", "loss", "train_loss", "val_loss",
    "acc", "accuracy", "val_acc", "train_acc", "best_val_acc", "best_acc",
    "time", "elapsed", "elapsed_time", "timestamp", "date", "runtime",
    "progress", "percent", "speed", "eta",
}

PARAM_HINT = re.compile(
    r"(batch[_ ]?size|lr|learning[_ ]?rate|weight[_ ]?decay|epochs?|"
    r"seed|optimizer|momentum|dropout|warmup|grad[_ ]?clip|"
    r"num[_ ]?layers?|hidden[_ ]?(?:size|dim)|heads?|"
    r"train[_ ]?batch|val[_ ]?batch|test[_ ]?batch|"
    r"max[_ ]?(?:len|length|tokens)|temperature|top[_ ]?p|"
    r"num[_ ]?workers|precision|fp16|bf16|amp)",
    re.I,
)

KV_RE = re.compile(
    r"^(?P<key>[A-Za-z][A-Za-z0-9_.\- ]{1,48}?)\s*[:=]\s*"
    r"(?P<val>[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?\s*[A-Za-z%µ/]*|true|false|True|False)\s*$"
)
LOG_KV_RE = re.compile(r"^(?P<key>[A-Za-z][\w.\- ]{0,48}?)\s*[=:]\s*(?P<val>\S.{0,120}?)\s*$")
SH_FLAG_RE = re.compile(r"--([A-Za-z0-9][\w\-]*)(?:[= ]([^\s'\"]+))?")
SH_ENV_RE = re.compile(r"^\s*export\s+([A-Za-z_][A-Za-z0-9_]*)=([^\s;#]+)")
PY_ARG_RE = re.compile(
    r"add_argument\(\s*['\"]--([\w\-]+)['\"](?P<rest>[^)]*?)\)",
    re.S,
)
PY_DEFAULT_RE = re.compile(r"default\s*=\s*([^,)\]]+)")
PY_CONST_RE = re.compile(r"^([A-Z][A-Z0-9_]{2,})\s*=\s*(.+?)\s*(?:#.*)?$")

PRIORITY = {"config": 3, "code": 2, "log": 1, "doc": 1, "text": 1}


def _line_of(lines, needle: str) -> int:
    for i, ln in enumerate(lines, 1):
        if needle in ln:
            return i
    return 1


def _mk(key, raw, file, line, quote, extractor, priority):
    nk = norm_key(key)
    if not nk or nk in SCALAR_KEYS_SKIP:
        return None
    if nk.startswith("_") or nk.isdigit():
        return None
    raw = str(raw).strip().strip(",").strip()
    if not raw or len(raw) > 200:
        return None
    quote = (quote or "").strip()
    if not quote or len(quote) > 400:
        return None
    if re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2}:\d{2}", raw):
        return None
    num, unit = split_value_unit(raw)
    value = canon_number(num)
    if value is not None:
        kind = "number"
    else:
        b = to_bool(raw)
        if b is not None:
            value, kind = ("true" if b else "false"), "bool"
        else:
            value, kind, unit = raw, "string", ""
    return {
        "key": nk,
        "raw": raw,
        "value": value,
        "kind": kind,
        "unit": unit,
        "source": {"file": file, "line": line, "quote": quote, "sha256_16": sha256_text(quote)[:16]},
        "extractor": extractor,
        "priority": priority,
    }


def _from_yaml(text, file):
    out = []
    for key, val, line in parse_scalars(text):
        c = _mk(key, val, file, line, text.splitlines()[line - 1], "yaml", PRIORITY["config"])
        if c:
            out.append(c)
    return out


def _flatten(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _flatten(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _flatten(v, f"{prefix}[{i}]")
    else:
        yield prefix, obj


def _from_json(text, file):
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    lines = text.splitlines()
    out = []
    for key, val in _flatten(data):
        full = re.sub(r"\[\d+\]", "", key)
        leaf = full.split(".")[-1]
        c = _mk(full, val, file, _line_of(lines, f'"{leaf}"'), "", "json", PRIORITY["config"])
        if c:
            out.append(c)
    return out


def _from_toml(text, file):
    try:
        data = tomllib.loads(text)
    except Exception:
        return []
    lines = text.splitlines()
    out = []
    for key, val in _flatten(data):
        full = re.sub(r"\[\d+\]", "", key)
        leaf = full.split(".")[-1]
        c = _mk(full, val, file, _line_of(lines, leaf), "", "toml", PRIORITY["config"])
        if c:
            out.append(c)
    return out


def _from_ini(text, file):
    out = []
    for i, ln in enumerate(text.splitlines(), 1):
        m = re.match(r"^\s*([A-Za-z][\w.\-]*)\s*[=:]\s*(.+?)\s*$", ln)
        if m:
            c = _mk(m.group(1), m.group(2), file, i, ln, "ini", PRIORITY["config"])
            if c:
                out.append(c)
    return out


def _from_log(text, file):
    out = []
    for i, ln in enumerate(text.splitlines(), 1):
        m = LOG_KV_RE.match(ln.strip())
        if not m:
            continue
        key, val = m.group("key").strip(), m.group("val").strip()
        if key.isdigit() or re.match(r"^\d", key):
            continue
        c = _mk(key, val, file, i, ln, "log", PRIORITY["log"])
        if c:
            out.append(c)
    return out


def _from_shell(text, file):
    out = []
    for i, ln in enumerate(text.splitlines(), 1):
        if ln.strip().startswith("#"):
            continue
        m = SH_ENV_RE.match(ln)
        if m:
            c = _mk(m.group(1), m.group(2), file, i, ln, "sh_env", PRIORITY["code"])
            if c:
                out.append(c)
        for fm in SH_FLAG_RE.finditer(ln):
            if fm.group(2) is None:
                continue
            c = _mk(fm.group(1), fm.group(2), file, i, ln, "sh_flag", PRIORITY["code"])
            if c:
                out.append(c)
    return out


def _from_python(text, file):
    out = []
    lines = text.splitlines()
    for m in PY_ARG_RE.finditer(text):
        rest = m.group("rest") or ""
        dm = PY_DEFAULT_RE.search(rest)
        if not dm:
            continue
        raw = dm.group(1).strip().strip("'\"")
        ln = text[: m.start()].count("\n") + 1
        c = _mk(m.group(1), raw, file, ln, lines[ln - 1] if ln - 1 < len(lines) else "", "py_argparse", PRIORITY["code"])
        if c:
            out.append(c)
    for i, ln in enumerate(lines, 1):
        m = PY_CONST_RE.match(ln.strip())
        if not m:
            continue
        c = _mk(m.group(1), m.group(2).strip().strip("'\""), file, i, ln, "py_const", PRIORITY["code"])
        if c:
            out.append(c)
    return out


def _from_doc(text, file):
    out = []
    for i, ln in enumerate(text.splitlines(), 1):
        s = ln.strip().lstrip("-*").strip()
        m = re.match(r"^\*\*([^*]{2,60})\*\*\s*[:：]\s*(.+)$", s)
        if m and PARAM_HINT.search(m.group(1)):
            c = _mk(m.group(1), m.group(2), file, i, ln, "md_bold", PRIORITY["doc"])
            if c:
                out.append(c)
            continue
        m = KV_RE.match(s)
        if m and PARAM_HINT.search(m.group("key")):
            c = _mk(m.group("key"), m.group("val"), file, i, ln, "md_kv", PRIORITY["doc"])
            if c:
                out.append(c)
    return out


def extract_candidates(index, allow_doc=True):
    out = []
    for m in index:
        if m["kind"] in ("binary", "noext"):
            continue
        ext = m["ext"]
        try:
            text = read_text(m["abs"])
        except OSError:
            continue
        if ext in (".yaml", ".yml"):
            out += _from_yaml(text, m["file"])
        elif ext == ".json":
            out += _from_json(text, m["file"])
        elif ext == ".toml":
            out += _from_toml(text, m["file"])
        elif ext in (".ini", ".cfg", ".conf"):
            out += _from_ini(text, m["file"])
        elif ext in (".log", ".out"):
            out += _from_log(text, m["file"])
        elif ext in (".sh", ".bash", ".zsh"):
            out += _from_shell(text, m["file"])
        elif ext == ".py":
            out += _from_python(text, m["file"])
        elif ext in (".md", ".markdown", ".txt", ".rst") and allow_doc:
            out += _from_doc(text, m["file"])
    return out


DATASET_PATTERNS = {
    "name": re.compile(r"^\s*(?:[-*]\s*)?(?:dataset|数据集)\s*[:：]\s*(.+?)\s*$", re.I),
    "version": re.compile(r"^\s*(?:[-*]\s*)?(?:version|版本)\s*[:：]\s*(.+?)\s*$", re.I),
    "size": re.compile(r"^\s*(?:[-*]\s*)?(?:size|规模|样本数)\s*[:：]\s*(.+?)\s*$", re.I),
    "split": re.compile(r"^\s*(?:[-*]\s*)?(?:split|划分)\s*[:：]\s*(.+?)\s*$", re.I),
    "split_seed": re.compile(r"^\s*(?:[-*]\s*)?(?:split[_ ]?seed|划分随机种子)\s*[:：]\s*(.+?)\s*$", re.I),
    "preprocess": re.compile(r"^\s*(?:[-*]\s*)?(?:preprocess|预处理)\s*[:：]\s*(.+?)\s*$", re.I),
}

CONTROL_PATTERNS = {
    "baseline": re.compile(r"^\s*(?:[-*]\s*)?(?:baseline|基线)\s*[:：]\s*(.+?)\s*$", re.I),
    "baseline_version": re.compile(r"^\s*(?:[-*]\s*)?(?:baseline[_ ]?version|基线版本)\s*[:：]\s*(.+?)\s*$", re.I),
    "budget": re.compile(r"^\s*(?:[-*]\s*)?(?:budget|budget[_ ]?parity|预算)\s*[:：]\s*(.+?)\s*$", re.I),
    "metric": re.compile(r"^\s*(?:[-*]\s*)?(?:metric|指标)\s*[:：]\s*(.+?)\s*$", re.I),
    "stat": re.compile(r"^\s*(?:[-*]\s*)?(?:stat|statistics|统计方式|重复次数)\s*[:：]\s*(.+?)\s*$", re.I),
}


def _structured(text, file, patterns):
    found = {}
    for i, ln in enumerate(text.splitlines(), 1):
        for field, rx in patterns.items():
            m = rx.match(ln)
            if m and field not in found:
                found[field] = {"value": m.group(1).strip(), "source": {"file": file, "line": i, "quote": ln.strip()}}
    return found


def extract_datasets(index):
    entry, sources = {}, {}
    for m in index:
        if m["kind"] not in ("doc", "text"):
            continue
        found = _structured(read_text(m["abs"]), m["file"], DATASET_PATTERNS)
        for k, v in found.items():
            if k not in entry:
                entry[k] = v["value"]
                sources[k] = v["source"]
    if not entry:
        return None
    return {"id": "D1", "fields": entry, "sources": sources}


def extract_controls(index):
    entry, sources = {}, {}
    for m in index:
        if m["kind"] not in ("doc", "text"):
            continue
        found = _structured(read_text(m["abs"]), m["file"], CONTROL_PATTERNS)
        for k, v in found.items():
            if k not in entry:
                entry[k] = v["value"]
                sources[k] = v["source"]
    if not entry:
        return None
    return {"id": "C1", "fields": entry, "sources": sources}


COMMAND_RE = re.compile(r"^\s*(?:python3?|torchrun|accelerate|deepspeed|bash|sh|conda|pip|git)\b")


def extract_commands(index, limit=20):
    cmds = []
    for m in index:
        if m["ext"] not in (".sh", ".bash", ".zsh", ".log", ".out", ".md", ".txt"):
            continue
        for i, ln in enumerate(read_text(m["abs"]).splitlines(), 1):
            s = ln.strip()
            if s.startswith("#") or s.startswith("//"):
                continue
            if COMMAND_RE.match(s) and len(s) < 300:
                cmds.append({"cmd": s, "source": {"file": m["file"], "line": i}})
                if len(cmds) >= limit:
                    return cmds
    return cmds


def extract_version_hints(index):
    hints = {}
    pats = {
        "python": re.compile(r"python(?:[_ ]?version)?\s*[:=]\s*([0-9]+\.[0-9]+(?:\.[0-9]+)?)", re.I),
        "cuda": re.compile(r"cuda(?:[_ ]?version)?\s*[:=]\s*([0-9]+\.[0-9]+)", re.I),
        "commit": re.compile(r"\bcommit\s*[:=]\s*([0-9a-f]{7,40})\b", re.I),
        "torch": re.compile(r"torch\s*[:=]\s*([0-9]+\.[0-9]+(?:\.[0-9]+)?)", re.I),
        "hardware": re.compile(
            r"\b(A100|H100|H800|A800|V100|A6000|RTX ?\d{4}|GTX ?\d{4}|TPU ?v\d)\b"
        ),
    }
    for m in index:
        if m["kind"] in ("binary", "noext"):
            continue
        text = read_text(m["abs"])
        for k, rx in pats.items():
            if k in hints:
                continue
            mm = rx.search(text)
            if mm:
                hints[k] = {"value": mm.group(1), "file": m["file"]}
    return hints
