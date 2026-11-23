"""Numeric firewall.

Conservation law (checked here):

    Numbers(rendered) == Numbers(substituted slots) U Whitelist

A numeric token is *bound* only when its character range lies inside a span
produced by the renderer.  A hand-typed number that merely happens to equal a
ledger value is still a violation: values must flow through slots, not prose.
"""

from __future__ import annotations

import bisect
import re
from pathlib import Path

from .util import canon_number, read_text

NUM_RE = re.compile(r"(?<![\w.])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?(?![\w])")

LIST_MARK = re.compile(r"^\s*\d+[.)]\s")
HEADING_NUM = re.compile(r"^#{1,6}\s+[\d.]+")
REF = re.compile(
    r"(?:Table|Figure|Fig\.|Eq\.|Equation|Section|Sec\.|Algorithm|Appendix)\s*\(?(\d+)\)?",
    re.I,
)


def _line_bounds(text, pos):
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    if end < 0:
        end = len(text)
    return start, end


def _whitelisted(text, start, end, token, allow):
    if canon_number(token) in allow:
        return True
    ls, le = _line_bounds(text, start)
    line = text[ls:le]
    m = re.match(r"^(\s*)(\d+)[.)]\s", line)
    if m and start == ls + len(m.group(1)) and token == m.group(2):
        return True
    # heading numbering: "## 3.2 ..."
    lm = re.match(r"^(\s*)(#{1,6})\s+([\d.]+)", line)
    if lm and start < ls + len(lm.group(0)) and token in lm.group(3):
        return True
    # cross references: Table 2 / Fig. 3 / Eq. (4)
    for rm in REF.finditer(line):
        if rm.group(1) == token:
            return True
    return False


def load_allowlist(path):
    p = Path(path) if path else None
    if not p or not p.exists():
        return set()
    allow = set()
    for ln in read_text(p).splitlines():
        s = ln.split("#", 1)[0].strip()
        c = canon_number(s)
        if c:
            allow.add(c)
    return allow


def check(rendered: str, spans, allow=None):
    allow = allow or set()
    starts = [s[0] for s in spans]
    violations = []

    def bound(pos):
        i = bisect.bisect_right(starts, pos) - 1
        if i < 0:
            return False
        s, e = spans[i][0], spans[i][1]
        return s <= pos < e

    for m in NUM_RE.finditer(rendered):
        tok = m.group(0)
        if bound(m.start()):
            continue
        if _whitelisted(rendered, m.start(), m.end(), tok, allow):
            continue
        ls, le = _line_bounds(rendered, m.start())
        line = rendered[ls:le].strip()
        violations.append({
            "code": "E_UNBOUND_NUMBER",
            "token": tok,
            "line": rendered.count("\n", 0, m.start()) + 1,
            "col": m.start() - ls + 1,
            "context": line[:160],
        })
    return violations
