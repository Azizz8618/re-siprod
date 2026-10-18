#!/usr/bin/env python3
"""Probe which SPAUD dispatch cases a *RED input fragment reaches.

SPAUD (the *RED formatter) dispatches on the token class returned by SCAN
through a 20-way computed GOTO (SPAUD.dtran, *0137B and *0350B).  This tool
runs SIPROD under dispak with PC coverage and reports which case targets were
executed.

Usage:
  tools/siprod_probe.py FRAGMENT...      each FRAGMENT is *RED body text;
                                         "\\n" separates lines
  tools/siprod_probe.py -f FILE...       whole input files (incl. *RED/*END)
  tools/siprod_probe.py -s PREFIX SUFFIX CHARS
                                         sub-command sweep: for each char c in
                                         CHARS run PREFIX+c+SUFFIX and group
                                         chars by the code executed beyond
                                         PREFIX+SUFFIX alone

Example:
  tools/siprod_probe.py '*SТЕКСТ' '*PТЕКСТ'
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import siprod_cov  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "tests" / "siprod" / "run.sh"

# SPAUD computed-GOTO targets, case number -> module-relative address
# (second table at *0350B differs only in case 7: *0673B instead of *0677B).
CASES = {i + 1: int(a, 8) for i, a in enumerate(
    "0375 0434 0441 0555 0611 0652 0677 0731 0735 0764 1014 1027 1070 1227 "
    "1267 1756 2201 2242 2333 2347".split())}
CASES_ALT = {7: 0o673}


def run(input_text: str) -> tuple[str, set[int], dict[str, dict[int, str]]]:
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "in.txt"
        cov = Path(d) / "cov.txt"
        inp.write_text(input_text)
        out = subprocess.run([str(RUN), "-C", str(cov), str(inp)],
                             capture_output=True, text=True).stdout
        bym = siprod_cov.by_module(siprod_cov.load_cov(str(cov)),
                                   siprod_cov.load_map())
    spaud = bym.get("SPAUD", {})
    hit = {c for c, a in CASES.items() if a in spaud}
    hit |= {c for c, a in CASES_ALT.items() if a in spaud}
    return out, hit, bym


def executed(bym) -> set[tuple[str, int]]:
    return {(m, o) for m, offs in bym.items() for o in offs}


def sweep(prefix: str, suffix: str, chars: str) -> int:
    def frag(t: str) -> str:
        return "*RED\n" + t.replace("\\n", "\n") + "\n*E\n*END\n"
    base = executed(run(frag(prefix + suffix))[2])
    groups: dict[frozenset, list[str]] = {}
    for c in chars:
        extra = frozenset(executed(run(frag(prefix + c + suffix))[2]) - base)
        groups.setdefault(extra, []).append(c)
    for extra, cs in sorted(groups.items(), key=lambda kv: len(kv[0])):
        mods: dict[str, int] = {}
        for m, _ in extra:
            mods[m] = mods.get(m, 0) + 1
        print(f"{''.join(cs):20} " + " ".join(f"{m}+{n}" for m, n in sorted(mods.items())))
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    if argv[0] == "-s":
        return sweep(*argv[1:4])
    files = argv[0] == "-f"
    base = run("*RED\n*E\n*END\n")[1]
    print(f"baseline cases: {sorted(base)}")
    for arg in argv[1:] if files else argv:
        text = Path(arg).read_text() if files else \
            "*RED\n" + arg.replace("\\n", "\n") + "\n*E\n*END\n"
        out, hit, _ = run(text)
        print(f"{arg!r:30} cases {sorted(hit - base)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
