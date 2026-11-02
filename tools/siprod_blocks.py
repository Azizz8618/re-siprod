#!/usr/bin/env python3
"""Показать блоки модуля СИПРОДа с автоименами - для разбора имён.

Печатает для каждой метки с автоматическим именем текст блока из
текста БЕМШ (команды с пояснениями), чтобы понять назначение блока и
назвать метку осмысленно.

Использование:
    tools/siprod_blocks.py МОДУЛЬ            # блоки с автоименами
    tools/siprod_blocks.py МОДУЛЬ --all      # все блоки
    tools/siprod_blocks.py МОДУЛЬ --word N   # блок вокруг слова N
"""

from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from siprod_be import info                                         # noqa: E402
from siprod_bemsh import parse_be                                 # noqa: E402
from siprod_labels import module_table                            # noqa: E402
from siprod_lib import Library                                    # noqa: E402

TXT = os.path.join(ROOT, "text")
IMAGE = os.path.join(ROOT, "siprod.bin")

AUTO = re.compile(r"^(ПЕРЕХОД|ПЕР_|ЦИКЛ_|ВОЗВРАТ|ЧТЕНИЕ|ЗАПИСЬ|СЧЁТ|"
                   r"В_МАГАЗИН|ИЗ_МАГАЗИНА|АДРЕС|СРАВНЕНИЕ|ВЫЧИТАНИЕ|"
                   r"СЛОЖЕНИЕ|ИСКЛЮЧАЮЩЕЕ_ИЛИ|КАДР|ПРОЦЕДУРА|ИЛИ|И)_")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("module")
    ap.add_argument("--all", action="store_true", help="все метки")
    ap.add_argument("--word", type=int, default=-1,
                    help="показать блоки вокруг слова с этим номером")
    args = ap.parse_args()

    lib = Library(IMAGE)
    name = args.module
    table = module_table(lib, name)
    ext, labels, exits, insns = info(lib, name)
    path = os.path.join(TXT, name.replace("*", "#") + ".be")
    _locsyms, _labs, instrs, _data = parse_be(path)
    text = {num: (instr, op) for num, instr, op, _lab in instrs}

    known = sorted(labels)
    for i, off in enumerate(known):
        nxt = known[i + 1] if i + 1 < len(known) else None
        word = off // 2
        nm = table.get(word)
        if nm is None:
            continue
        if not args.all and not AUTO.match(nm):
            continue
        if args.word >= 0 and abs(word - args.word) > 5:
            continue
        print("--- слово %d (команда %d): %s   [исходное: %s]"
              % (word, off, nm, labels[off]))
        for o, _half in insns:
            if o < off:
                continue
            if nxt is not None and o >= nxt:
                break
            instr, op = text.get(o, ("?", "?"))
            print("    %-6s %s" % (instr, op))
    return 0


if __name__ == "__main__":
    sys.exit(main())
