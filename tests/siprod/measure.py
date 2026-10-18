#!/usr/bin/env python3
# Filter: prefix each line with its first and last non-blank column (1-based).
# Usage: tests/siprod/frag.sh ... | tests/siprod/measure.py [-s] [-f]
#   -s  squeeze runs of empty lines into one "(n empty)" line
#   -f  drop frame-only lines ("I   I") and blank frame borders
import sys
squeeze = "-s" in sys.argv
noframe = "-f" in sys.argv
blank = 0


def flush():
    global blank
    if blank:
        print(f"        ({blank} empty)" if squeeze and blank > 1 else "  1-  0 |")
        if not squeeze:
            for _ in range(blank - 1):
                print("  1-  0 |")
    blank = 0


for l in sys.stdin:
    l = l.rstrip("\n")
    if noframe and l.strip(" I") == "":
        l = ""
    if l.strip() == "":
        blank += 1
        continue
    flush()
    s = len(l) - len(l.lstrip())
    print(f"{s + 1:3}-{len(l.rstrip()):3} |{l}")
flush()
