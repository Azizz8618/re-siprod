#!/usr/bin/env python3
"""Собрать тексты МАДЛЕН: осмысленные имена меток и пояснения.

Тексты МАДЛЕН в каталоге madlen/ - исходники для штатного компилятора
МАДЛЕН.  Собираются они так:

1. из madlen-gen/ берётся результат разбора модуля дизассемблером dtran
   (метки там названы номерами слов: `*0032B`);
2. меткам даются осмысленные имена (tools/siprod_labels.py): по
   содержимому помеченного блока - вызов внешней подпрограммы,
   обращение к общему блоку, работа с переменной, возврат, цикл; ручные
   имена (LABEL_NAMES) выигрывают;
3. добавляются пояснения: шапка модуля и пояснения к процедурам из
   ручных заметок (tools/siprod_notes.py).

Комментарий в языке МАДЛЕН - строка, начинающаяся с `C`.

Тексты, однажды наполненные, не перезаписываются: сборка идёт только
для тех модулей, где пояснений ещё нет, иначе - с --force.  Каталог
madlen-gen/ (результат разбора) при этом не трогается, поэтому обычная
пересборка (`make madlen`) не затирает правку текстов.

Использование:
    tools/siprod_madlen_notes.py             # собрать madlen/
    tools/siprod_madlen_notes.py --force     # пересобрать заново
    tools/siprod_madlen_notes.py --check     # только проверить
"""

from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from siprod_labels import module_table                       # noqa: E402
from siprod_lib import Library                               # noqa: E402
from siprod_notes import LABEL_NOTES, MODULE_NOTES            # noqa: E402

GEN = os.path.join(ROOT, "madlen-gen")
DST = os.path.join(ROOT, "madlen")
TXT = os.path.join(ROOT, "text")
IMAGE = os.path.join(ROOT, "siprod.bin")

LABEL_RE = re.compile(r"\*([0-7]+)B")


def header(module):
    """Шапка текста БЕМШ - строки комментария МАДЛЕН."""
    path = os.path.join(TXT, module.replace("*", "#") + ".be")
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if line.startswith("***"):
            break
        if line.startswith("*"):
            out.append(line[1:].strip())
        else:
            break
    return out


def comment(text):
    """Строка комментария МАДЛЕН."""
    return "C" + text


def module_notes(module):
    """Пояснения к модулю: строки текста."""
    out = list(MODULE_NOTES.get(module, []))
    for l in header(module):
        if l.startswith("Источник:") or l.startswith("Длина при загрузке:"):
            continue                       # это и так есть в шапке
        out.append(l)
    return out


def label_notes(lib, module):
    """Пояснения к меткам модуля: имя метки в тексте МАДЛЕН -> текст.

    Ключ LABEL_NOTES - смещение команды от начала модуля, а метка
    находится по номеру слова (в слове две команды).
    """
    notes = LABEL_NOTES.get(module, {})
    if not notes:
        return {}
    table = module_table(lib, module)
    out = {}
    for cmd, note in notes.items():
        name = table.get(cmd // 2)
        if name:
            out[name] = note
    return out


def rename(text, table):
    """Переименовать метки *NNNB в тексте МАДЛЕН."""
    mapping = {"%04o" % word: nm for word, nm in table.items()}

    def repl(mo):
        return mapping.get(mo.group(1), mo.group(0))

    return LABEL_RE.sub(repl, text)


def build(lib, module):
    """Текст МАДЛЕН с именами меток и пояснениями."""
    gen = os.path.join(GEN, module.replace("*", "#") + ".madlen")
    if not os.path.exists(gen):
        return None
    table = module_table(lib, module)
    text = rename(open(gen, encoding="utf-8").read(), table)
    lines = text.splitlines()
    notes = label_notes(lib, module)
    head = []
    for l in module_notes(module):
        head.append(comment(l))
    if head:
        head.append(comment(""))
    out = list(head)
    for line in lines:
        m = re.match(r"\s*([A-Za-zА-ЯЁ][A-Za-zА-ЯЁ0-9_]*):", line)
        if m:
            note = notes.get(m.group(1))
            if note:
                out.append(comment(" " + note))
        out.append(line)
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("modules", nargs="*", help="модули (по умолчанию - все)")
    ap.add_argument("--force", action="store_true",
                    help="пересобрать уже наполненные тексты")
    ap.add_argument("--check", action="store_true",
                    help="только проверить, что пояснения на месте")
    args = ap.parse_args()
    os.makedirs(DST, exist_ok=True)
    lib = Library(IMAGE)
    done = miss = 0
    for f in sorted(os.listdir(GEN) if os.path.isdir(GEN) else []):
        if not f.endswith(".madlen"):
            continue
        module = f[:-7]
        # в именах файлов '*' заменён на '#', в библиотеке - наоборот
        if args.modules and module not in args.modules \
                and module.replace("#", "*") not in args.modules:
            continue
        module = module.replace("#", "*")
        path = os.path.join(DST, f)
        if os.path.exists(path) and not args.force:
            done += 1
            continue
        text = build(lib, module)
        if text is None:
            continue
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        done += 1
    print("текстов в madlen/: %d" % done)
    if args.check:
        bad = 0
        for f in sorted(os.listdir(DST)):
            if not f.endswith(".madlen"):
                continue
            text = open(os.path.join(DST, f), encoding="utf-8").read()
            if not text.lstrip().startswith("C"):
                bad += 1
                print("   без пояснений: %s" % f)
        print("без пояснений: %d" % bad)
    return 0


if __name__ == "__main__":
    sys.exit(main())
