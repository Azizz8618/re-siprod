#!/usr/bin/env python3
"""Осмысленные имена меток в текстах МАДЛЕН.

Модуль СИПРОДа, разобранный дизассемблером dtran в формат МАДЛЕН,
содержит метки вида `*0032B` - это номер слова в модуле, никак не
связанный с тем, что делает помеченный участок кода.  Инструмент даёт
меткам имена по сути дела (как вычисляет tools/siprod_labels.py) и
записывает их в тексты каталога madlen/.

Каталог madlen-gen/ (результат разбора) не трогается, и уже
переименованные тексты повторно не переписываются, если их правка
сделана вручную: --force позволяет переименовать заново.

Использование:
    tools/siprod_madlen_labels.py             # переименовать во всех модулях
    tools/siprod_madlen_labels.py SCHEMA SPAUD
    tools/siprod_madlen_labels.py --check      # только показать имена
"""

from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from siprod_labels import module_table                      # noqa: E402
from siprod_lib import Library                              # noqa: E402

MADLEN = os.path.join(ROOT, "madlen")
GEN = os.path.join(ROOT, "madlen-gen")
IMAGE = os.path.join(ROOT, "siprod.bin")

LABEL_RE = re.compile(r"\*([0-7]+)B")


def rename_text(text, names):
    """Переименовать метки *NNNB в тексте МАДЛЕН."""
    mapping = {"%04o" % word: nm for word, nm in names.items()}

    def repl(mo):
        return mapping.get(mo.group(1), mo.group(0))

    return LABEL_RE.sub(repl, text)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("modules", nargs="*", help="модули (по умолчанию - все)")
    ap.add_argument("--src", default=MADLEN, help="каталог с текстами")
    ap.add_argument("--gen", default=GEN, help="каталог с исходным разбором")
    ap.add_argument("--image", default=IMAGE, help="образ библиотеки")
    ap.add_argument("--check", action="store_true",
                    help="только показать имена, ничего не записывать")
    ap.add_argument("--force", action="store_true",
                    help="переименовать заново, даже если метки уже названы")
    args = ap.parse_args()
    lib = Library(args.image)
    names = args.modules or sorted(lib.objects)
    total = 0
    for mod in names:
        if mod not in lib.objects:
            print("нет модуля: %s" % mod, file=sys.stderr)
            continue
        fname = mod.replace("*", "#") + ".madlen"
        path = os.path.join(args.src, fname)
        if not os.path.exists(path):
            path = os.path.join(args.gen, fname)
        if not os.path.exists(path):
            continue
        text = open(path, encoding="utf-8").read()
        if not args.force and not LABEL_RE.search(text):
            continue                      # метки уже переименованы
        table = module_table(lib, mod)
        new = rename_text(text, table)
        if new == text:
            continue
        total += 1
        if args.check:
            print("=== %s" % mod)
            for word in sorted(table):
                print("   %04o  %s" % (word, table[word]))
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new)
            print("%-10s: меток названо %d" % (mod, len(table)))
    if not args.check:
        print("переименовано модулей: %d" % total)


if __name__ == "__main__":
    main()
