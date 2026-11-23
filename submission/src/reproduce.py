#!/usr/bin/env python3
"""One-click reproduction of the bundled mini example.

This is the entrypoint declared for the package: it rebuilds
`examples/mini/work/` and `examples/mini/out/` from the synthetic case and the
slot draft, then writes the real console log to `execution/run.log`.

The example is synthetic and is labelled as such everywhere; it is not a
benchmark result and carries no score.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run as pkrun  # noqa: E402
from pk import emit  # noqa: E402


def main() -> int:
    case = ROOT / "examples" / "mini" / "case.json"
    work = ROOT / "examples" / "mini" / "work"
    out = ROOT / "examples" / "mini" / "out"
    draft = ROOT / "examples" / "mini" / "draft.src.md"

    for d in (work, out):
        shutil.rmtree(d, ignore_errors=True)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        a = pkrun.analyze(case)
        rc_init = pkrun.cmd_init(a, work)
        rc_check = pkrun.cmd_check(a, work, out, draft, None)

    # `work/` is a runtime intermediate; the shipped example keeps only `out/`.
    shutil.rmtree(work, ignore_errors=True)
    pack = emit.pack_check(ROOT)
    log = buf.getvalue().strip()
    header = (
        "# reproduce.py — synthetic mini example (not a benchmark result)\n"
        f"# case: {case.as_posix()}\n"
        f"# init rc={rc_init}  check rc={rc_check}\n"
        f"# pack: {json.dumps(pack, ensure_ascii=False)}\n"
        "# --- console ---\n"
    )
    (ROOT / "execution").mkdir(exist_ok=True)
    (ROOT / "execution" / "run.log").write_text(header + log + "\n", encoding="utf-8", newline="\n")

    result = out / "result.json"
    print(json.dumps({
        "rc_init": rc_init,
        "rc_check": rc_check,
        "out": str(out),
        "result_json": result.exists(),
        "pack_ok": pack["ok"],
        "log": str(ROOT / "execution" / "run.log"),
    }, ensure_ascii=False, indent=2))
    return 1 if (rc_init or rc_check == 1) else 0


if __name__ == "__main__":
    sys.exit(main())
