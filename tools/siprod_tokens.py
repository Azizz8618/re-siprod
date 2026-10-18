#!/usr/bin/env python3
"""Count SIPROD *RED control sequences in documents, using the command grammar
established by experiment (notes/commands.md), and list sequences that do
not fit it.

Usage: tools/siprod_tokens.py FILE...

Cyrillic letters that share a code with Latin ones (А В Е К М Н О Р С Т Х)
are folded to Latin first, as SIPROD sees them.
"""

from __future__ import annotations

import re
import sys
from collections import Counter

FOLD = str.maketrans("АВЕКМНОРСТХ", "ABEKMHOPCTX")

# Order matters: longer forms first.  Groups: (number) (command).
COMMAND = re.compile(r"""\*(\d*)(
      ST[APGON] | ST(?=[\s\d]) | SL
    | MCS | MCP | MD | MF | M= | M
    | R[GUCLFT]
    | OLR | ORU
    | N[NFTS/] | N
    | K\d+
    | [STP/GCFHDEW(]
    )""", re.X)


def scan(text: str, counts: Counter, bad: Counter) -> None:
    for line in text.splitlines():
        line = line.translate(FOLD)
        if line.startswith("*") and line[1:4] in ("RED", "END"):
            continue
        i = 0
        while (j := line.find("*", i)) >= 0:
            m = COMMAND.match(line, j)
            if m:
                num, cmd = m.groups()
                key = ("n" if num else "") + (re.sub(r"\d+", "n", cmd))
                counts[key] += 1
                i = m.end()
                # literal tails: *D takes the rest of the card, *nH n chars
                if cmd == "D":
                    break
                if cmd == "H":
                    i += int(num) if num else 1
                elif cmd in ("C", "F", "RF") or cmd.startswith("K"):
                    i += 1          # the repeated/fill character
            else:
                bad[line[j:j + 6]] += 1
                i = j + 1


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    counts: Counter = Counter()
    bad: Counter = Counter()
    for path in argv:
        with open(path, encoding="utf-8-sig") as f:
            scan(f.read(), counts, bad)
    for k, n in counts.most_common():
        print(f"{'*' + k:8} {n}")
    if bad:
        print("\nunparsed:")
        for k, n in bad.most_common():
            print(f"  {k!r:12} {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
