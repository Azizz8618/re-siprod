#!/usr/bin/env python3
# Filter: prefix each line with its first and last non-blank column (1-based).
# Usage: tests/siprod/frag.sh ... | tests/siprod/measure.py
import sys
for l in sys.stdin:
    l = l.rstrip("\n")
    s = len(l) - len(l.lstrip())
    print(f"{s + 1:3}-{len(l.rstrip()):3} |{l}")
