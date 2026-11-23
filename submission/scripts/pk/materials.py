"""Material index: every input file, its kind, and a stable locator scheme.

A locator is always `<relative/file>:<line>`.  Quotes are stored next to the
locator so the ledger can be re-read and verified later.
"""

from __future__ import annotations

from pathlib import Path

from .util import BINARY_EXTS, TEXT_EXTS, iter_files, rel_posix, sha256_bytes, read_text

KIND_BY_EXT = {
    ".yaml": "config", ".yml": "config", ".json": "config", ".toml": "config",
    ".ini": "config", ".cfg": "config", ".conf": "config",
    ".log": "log", ".out": "log",
    ".md": "doc", ".markdown": "doc", ".txt": "doc", ".rst": "doc", ".tex": "doc",
    ".py": "code", ".sh": "code", ".bash": "code", ".zsh": "code",
    ".csv": "data", ".tsv": "data",
}


def build_index(roots, exclude=(), exclude_dirs=(".git", "node_modules", "__pycache__",
                                               ".venv", "venv", "work", "out", "output", "pk"),
                exclude_names=("case.json", "draft.src.md", "draft.md", "draft.rejected.md")):
    exclude = {Path(e).resolve() for e in exclude}
    files, seen = [], set()
    for root in roots:
        root = Path(root).resolve()
        for p in iter_files(root):
            rp = p.resolve()
            if rp in seen or rp in exclude:
                continue
            rel_parts = p.relative_to(root).parts
            if any(part in exclude_dirs for part in rel_parts[:-1]):
                continue
            if p.name in exclude_names:
                continue
            seen.add(rp)
            files.append((rp, rel_posix(p, root), root))
    index = []
    for path, rel, root in files:
        ext = path.suffix.lower()
        if ext in BINARY_EXTS:
            kind = "binary"
        elif ext in TEXT_EXTS:
            kind = KIND_BY_EXT.get(ext, "text")
        else:
            kind = "text" if ext else "noext"
        try:
            size = path.stat().st_size
            digest = sha256_bytes(path.read_bytes())[:16]
        except OSError:
            size, digest = 0, ""
        index.append({
            "file": rel,
            "abs": str(path),
            "ext": ext,
            "kind": kind,
            "size": size,
            "sha256_16": digest,
            "root": str(root),
        })
    return index


def text_files(index):
    return [m for m in index if m["kind"] not in ("binary", "noext")]


def load_lines(index):
    """Cache file -> list[str] for locator lookups."""
    cache = {}
    for m in text_files(index):
        cache[m["file"]] = read_text(m["abs"]).splitlines()
    return cache
