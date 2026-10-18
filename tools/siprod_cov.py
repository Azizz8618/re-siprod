#!/usr/bin/env python3
"""Attribute a dispak PC coverage map to SIPROD modules.

Usage:
  tools/siprod_cov.py COV                 per-module summary of executed words
  tools/siprod_cov.py COV MODULE...       executed module-relative addresses
                                          (octal, as in MODULE.dtran)
  tools/siprod_cov.py -d BASE COV         modules/addresses executed in COV but
                                          not in BASE (minimal-pair diff)

COV files come from `tests/siprod/run.sh -C COV INPUT` (dispak).  Module
addresses are taken from tests/siprod/loadmap-dispak.txt (regenerate with
tests/siprod/loadmap.sh); the dubna map differs past the FORTRAN runtime.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOADMAP = ROOT / "tests" / "siprod" / "loadmap-dispak.txt"

ENTRY_RE = re.compile(r"(\S+)\s+(?:([CE])\s+)?([0-7]{5})\b")


def load_map() -> list[tuple[int, str]]:
    """Return sorted (address, module) for code modules (not commons/entries)."""
    mods = []
    for line in LOADMAP.read_text().splitlines():
        for name, kind, addr in ENTRY_RE.findall(line):
            if kind in ("C", "E"):
                continue
            mods.append((int(addr, 8), name))
    mods.sort()
    return mods


def load_cov(path: str) -> dict[int, str]:
    cov = {}
    for line in Path(path).read_text().splitlines():
        addr, flags = line.split(": ")
        if flags != "--":
            cov[int(addr, 8)] = flags.strip()
    return cov


def module_of(addr: int, mods: list[tuple[int, str]]) -> tuple[str, int]:
    name, base = "?", 0
    for a, n in mods:
        if a > addr:
            break
        name, base = n, a
    return name, addr - base


def by_module(cov: dict[int, str], mods) -> dict[str, dict[int, str]]:
    res: dict[str, dict[int, str]] = {}
    for addr, flags in sorted(cov.items()):
        name, off = module_of(addr, mods)
        res.setdefault(name, {})[off] = flags
    return res


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    mods = load_map()
    if argv[0] == "-d":
        base = by_module(load_cov(argv[1]), mods)
        new = by_module(load_cov(argv[2]), mods)
        for name, offs in new.items():
            extra = sorted(set(offs) - set(base.get(name, {})))
            if extra:
                print(f"{name:8} +{len(extra):4}  " + " ".join(f"{o:o}" for o in extra))
        for name, offs in base.items():
            gone = sorted(set(offs) - set(new.get(name, {})))
            if gone:
                print(f"{name:8} -{len(gone):4}  " + " ".join(f"{o:o}" for o in gone))
        return 0
    bym = by_module(load_cov(argv[0]), mods)
    if len(argv) == 1:
        for name, offs in sorted(bym.items(), key=lambda kv: min(kv[1])):
            print(f"{name:8} {len(offs):5}")
        return 0
    for name in argv[1:]:
        offs = bym.get(name, {})
        print(f"{name}: " + " ".join(f"{o:o}{'' if f == 'LR' else ':' + f.strip()}"
                                     for o, f in sorted(offs.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
