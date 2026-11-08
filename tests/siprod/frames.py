#!/usr/bin/env python3
# Report frames (".-----." boxes drawn by *RG and the generator modes) in
# SIPROD output: columns, width, height in lines, and page headers inside.
# Usage: tests/siprod/frag.sh ... | tests/siprod/frames.py
import re
import sys

rows = [l.rstrip("\n") for l in sys.stdin]
for i, line in enumerate(rows):
    for m in re.finditer(r"\.-{5,}\.", line):
        s, e = m.start(), m.end() - 1
        # a frame top: the matching bottom is the next row with a border at s..e
        for j in range(i + 1, len(rows)):
            if rows[j][s:e + 1] == line[s:e + 1]:
                inside = [r[s + 1:e] for r in rows[i + 1:j]]
                hdr = [h for r in inside for h in re.findall(r"-\s*\d+ -", r)]
                print("frame cols %d-%d w=%d h=%d %s" % (s + 1, e + 1, e - s + 1, j - i + 1, " ".join(hdr)))
                break
