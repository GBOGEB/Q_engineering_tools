#!/usr/bin/env python3
"""Read pages from an engine projection.txt, optionally filtered by a regex.

    python page_reader.py <out>/LKT/projection.txt 193 207
    python page_reader.py <out>/ALAT/projection.txt 1 610 "noise|vibration"
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

MARKER = re.compile(r"<PARSED TEXT FOR PAGE: (\d+) / \d+>\n")


def pages(projection: Path) -> dict[int, str]:
    parts = MARKER.split(projection.read_text(encoding="utf-8"))
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts), 2)}


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    pg = pages(Path(argv[0]))
    first, last = int(argv[1]), int(argv[2])
    pat = re.compile(argv[3], re.I) if len(argv) > 3 else None
    for p in range(first, last + 1):
        lines = [ln for ln in pg.get(p, "").splitlines() if ln.strip()]
        if pat:
            lines = [ln for ln in lines if pat.search(ln)]
            if not lines:
                continue
        print(f"=== p{p}")
        print("\n".join(re.sub(r"[ \t]{3,}", "  ", ln) for ln in lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
