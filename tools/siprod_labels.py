#!/usr/bin/env python3
"""List labelled code in static SIPROD modules that no regression case executes.

Usage: tools/siprod_labels.py [MODULE...]      (default: SPAUD FIRCAR STAATP COMANN)

Runs every tests/siprod/cases/*.txt under dispak with coverage, unions the
executed addresses, and prints each label of MODULE.dtran (lines "*NNNNB:")
that was never executed.  Labels whose code calls KLAIDA within a few
instructions are marked "error", as they are expected to be unreached by the
non-error cases.  Overlay modules are not in the static load map and cannot
be checked this way.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import siprod_probe  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LABEL = re.compile(r"^ \*([0-7]{4})B:(.*)$")


def labels(module: str) -> list[tuple[int, list[str]]]:
    lines = (ROOT / f"{module}.dtran").read_text().splitlines()
    res = []
    for i, line in enumerate(lines):
        m = LABEL.match(line)
        if m and not re.search(r",(INT|ISO|OCT|LOG|BSS),", m.group(2)):
            res.append((int(m.group(1), 8), [m.group(2)] + lines[i + 1:i + 5]))
    return res


def main(argv: list[str]) -> int:
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    modules = argv or ["SPAUD", "FIRCAR", "STAATP", "COMANN"]
    executed: dict[str, set[int]] = {}
    for case in sorted((ROOT / "tests" / "siprod" / "cases").glob("*.txt")):
        for mod, offs in siprod_probe.run(case.read_text())[2].items():
            executed.setdefault(mod, set()).update(offs)
    for mod in modules:
        missed = [(a, body) for a, body in labels(mod) if a not in executed.get(mod, set())]
        print(f"{mod}: {len(missed)} unexecuted labels")
        for a, body in missed:
            tag = "error" if any("KLAIDA" in b for b in body) else ""
            print(f"  {a:04o} {tag:5} {body[0].strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
