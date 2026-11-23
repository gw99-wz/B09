"""A deliberately small YAML subset parser (no PyYAML dependency).

Supports the shapes that matter for experiment configs:
  key: value
  nested:
    key: value
  list:
    - item
  - key: value      (list of mappings)
Comments (#) and quoted scalars are handled; anchors/flow maps are not.
"""

from __future__ import annotations

import re

KEY_RE = re.compile(r"^(?P<dash>-\s+)?(?P<key>[^:#][^:]*?)\s*:\s*(?P<val>.*)$")


def _strip_comment(line: str) -> str:
    """Strip a trailing comment, ignoring '#' inside quotes."""
    in_s = in_d = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_d:
            in_s = not in_s
        elif ch == '"' and not in_s:
            in_d = not in_d
        elif ch == "#" and not in_s and not in_d:
            if i == 0 or line[i - 1] in " \t":
                return line[:i].rstrip()
    return line.rstrip()


def _unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        return v[1:-1]
    return v


def parse_scalars(text: str):
    """Yield (dotted_key, raw_value, line_no) for scalar leaves."""
    stack = []  # list[(indent, key)]
    for lineno, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.replace("\t", "    ")
        stripped = _strip_comment(line)
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        body = stripped.strip()
        m = KEY_RE.match(body)
        if not m:
            continue
        key = _unquote(m.group("key").strip())
        val = _unquote(m.group("val").strip())
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if val == "":
            stack.append((indent, key))
            continue
        path = [k for _, k in stack] + [key]
        yield ".".join(path), val, lineno
