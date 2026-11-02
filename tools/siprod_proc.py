#!/usr/bin/env python3
"""Отчёт по процедурам модуля СИПРОДа - для написания пояснений.

Для каждой процедуры (блока команд, заканчивающегося безусловным
переходом) печатается: смещение слова, метка, команды блока с
пояснениями из текста БЕМШ и список внешних символов, на которые
блок ссылается.

Использование:
    tools/siprod_proc.py МОДУЛЬ [--all]
"""

from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from siprod_be import decode, info                          # noqa: E402
from siprod_bemsh import OPS, parse_be                   # noqa: E402
from siprod_labels import module_table                     # noqa: E402
from siprod_lib import Library                             # noqa: E402

TXT = os.path.join(ROOT, "text")
IMAGE = os.path.join(ROOT, "siprod.bin")


def module_header(name):
    """Шапка модуля из текста БЕМШ (назначение, внешние символы)."""
    path = os.path.join(TXT, name.replace("*", "#") + ".be")
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if line.startswith("***"):
            break
        if line.startswith("*"):
            out.append(line[1:].strip())
    return out


def bemsh_comments(name):
    """Пояснения к командам из текста БЕМШ.

    Текст БЕМШ: `МНЕМОНИКА ОПЕРАНД ,комментарий`.  Разборщик
    parse_be отдаёт только операнд, поэтому комментарии читаются из
    строк файла напрямую.  Разбор повторяет правила parse_be: строка
    «СТАРТ», объявления «КОНД»/«ПАМ» и «ФИНИШ» командами не являются.
    """
    path = os.path.join(TXT, name.replace("*", "#") + ".be")
    out = {}
    if not os.path.exists(path):
        return out
    num = 0
    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        if line.startswith("***") or line.startswith("*"):
            continue
        # комментарий - часть после запятой, если перед ней 2+ пробелов
        m = re.search(r"\s{2,},(.*)$", line)
        comment = m.group(1).strip() if m else ""
        code = re.sub(r"\s{2,},.*$", "", line).rstrip()
        if not code.strip():
            continue
        parts = code.split(None, 1)
        first = parts[0]
        rest = parts[1].strip() if len(parts) > 1 else ""
        if len(parts) > 1 and parts[1].split(None, 1)[0].upper() in ("КОНД", "ПАМ"):
            continue                       # объявление данных
        if first.upper() == "ФИНИШ":
            continue
        if first.upper() == "СТАРТ":
            continue                       # вход в модуль, не команда
        if re.match(r"^[А-ЯЁA-Z][А-ЯЁA-Z0-9]*$", first) and first.upper() not in OPS:
            if not rest:
                continue                   # метка без команды
            p2 = rest.split(None, 1)
            if p2[0].upper() == "СТАРТ":
                continue
            out[num] = (p2[0].upper(), comment)
            num += 1
            continue
        out[num] = (first.upper(), comment)
        num += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("module")
    ap.add_argument("--all", action="store_true",
                    help="все блоки, а не только процедуры")
    args = ap.parse_args()

    lib = Library(IMAGE)
    name = args.module
    ext, labels, exits, insns = info(lib, name)
    table = module_table(lib, name)
    bemsh = bemsh_comments(name)

    print("########## МОДУЛЬ %s" % name)
    for line in module_header(name):
        if line:
            print("# %s" % line)
    print()

    known = sorted(labels)
    for i, off in enumerate(known):
        nxt = known[i + 1] if i + 1 < len(known) else None
        word = off // 2
        nm = table.get(word, labels[off])
        cmds = [(o, h) for o, h in insns if o >= off and (nxt is None or o < nxt)]
        if not cmds:
            continue
        last = decode(cmds[-1][1])
        is_proc = (last["name"] or "").upper() == "ПБ"
        if not is_proc and not args.all:
            continue
        print("--- слово 0o%o (команда %d)  метка %s%s"
              % (word, off, nm, "   [ПРОЦЕДУРА]" if is_proc else ""))
        for o, h in cmds:
            instr, note = bemsh.get(o, ("?", ""))
            print("    %-6s %-30s %s" % (instr, note, ""))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
