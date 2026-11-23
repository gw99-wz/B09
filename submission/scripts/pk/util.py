"""Shared helpers: canonical numbers, units, file IO, slugs.

Everything here is deterministic and dependency-free so the Skill runs on the
pinned evaluator image without extra installs.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

TEXT_EXTS = {
    ".md", ".markdown", ".txt", ".text", ".rst", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".conf", ".log", ".out", ".csv", ".tsv",
    ".py", ".sh", ".bash", ".zsh", ".tex", ".bib", ".html", ".xml",
}

BINARY_EXTS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".zip", ".gz", ".7z",
    ".docx", ".xlsx", ".pptx", ".odt", ".bin", ".pt", ".pth", ".ckpt",
    ".npy", ".npz", ".pkl", ".parquet", ".feather",
}

NUMBER_RE = re.compile(r"^[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?$")
UNIT_RE = re.compile(
    r"^(?P<num>[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s*"
    r"(?P<unit>%|‰|ms|s|sec|secs|seconds|min|mins|minutes|h|hours|"
    r"KB|MB|GB|TB|B|bytes|KiB|MiB|GiB|"
    r"px|pixels|images|samples|examples|tokens|steps|epochs|epoch|"
    r"layers|heads|dims|dim|bit|bits|W|kW|V|A|Hz|kHz|MHz|GHz|"
    r"°C|C|K|mm|cm|m|km|µm|nm|mL|L|µL|g|mg|µg|kg|mol|M|mM|µM|nM)?$"
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_text(path) -> str:
    """Read a text file tolerating BOM / UTF-8 / GB18030 / Latin-1."""
    p = Path(path)
    data = p.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace")


def write_text(path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")


def write_json(path, obj) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def iter_files(root, skip_dirs=(".git", "node_modules", "__pycache__", ".venv", "venv")):
    root = Path(root)
    if not root.exists():
        return []
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fn in filenames:
            p = Path(dirpath) / fn
            if p.is_file():
                out.append(p)
    return sorted(out)


def rel_posix(path, root) -> str:
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


def canon_number(raw) -> str | None:
    """Canonical decimal string, or None when not a plain number.

    Accepted: 64, 64.0, -1, 1e-3, 1E-3, 1,000 (comma stripped by caller).
    Returns the shortest exact decimal form so 1e-3 == 0.001 == 0.0010.
    """
    s = str(raw).strip().strip('"').strip("'")
    if not NUMBER_RE.match(s):
        return None
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    if d == d.to_integral_value():
        return str(int(d))
    return format(d.normalize(), "f")


def split_value_unit(raw: str):
    """Split '64 samples' -> ('64', 'samples'); '1e-3' -> ('1e-3', '')."""
    s = str(raw).strip().strip('"').strip("'")
    m = UNIT_RE.match(s)
    if not m:
        return s, ""
    return m.group("num"), (m.group("unit") or "")


def to_bool(raw):
    s = str(raw).strip().lower()
    if s in ("true", "yes", "on"):
        return True
    if s in ("false", "no", "off"):
        return False
    return None


def slug(key: str) -> str:
    s = re.sub(r"[^0-9A-Za-z]+", "_", str(key)).strip("_").lower()
    if not s:
        s = "x" + hashlib.sha256(str(key).encode("utf-8")).hexdigest()[:8]
    return s


def norm_key(key: str) -> str:
    s = str(key).strip().strip('"').strip("'")
    s = s.replace(".", "_").replace("-", "_").replace(" ", "_").replace("/", "_")
    s = re.sub(r"[^\w]+", "_", s, flags=re.UNICODE)
    s = re.sub(r"_+", "_", s).strip("_")
    return s.lower() or "unknown"


def now_utc() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fmt_value(raw: str, unit: str = "") -> str:
    """Human-readable value used when rendering a slot."""
    raw = "" if raw is None else str(raw)
    if unit and unit not in ("1", "dimensionless"):
        return f"{raw} {unit}"
    return raw
