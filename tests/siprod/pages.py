#!/usr/bin/env python3
# Summarize page layout of SIPROD output: one token per page number line,
# "n:F" where F is where the "- n -" header sits on the sheet:
#   L/R = left/right page of the normal 2-up sheet, A = format A (one page),
#   W = wide format, ? = elsewhere.
# Usage: tests/siprod/frag.sh ... | tests/siprod/pages.py
import re
import sys

out = []
for line in sys.stdin:
    for m in re.finditer(r"-\s*(\d+) -", line):
        c = m.start() + 1
        f = "A" if 38 <= c <= 45 else "W" if 58 <= c <= 66 else "L" if c < 38 else "R" if c >= 90 else "?"
        out.append(f"{m.group(1)}:{f}")
print(" ".join(out))
