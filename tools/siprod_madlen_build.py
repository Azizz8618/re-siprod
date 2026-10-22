#!/usr/bin/env python3
"""Собрать тексты МАДЛЕН: имена меток, шапка и пояснения.

Тексты МАДЛЕН в каталоге madlen/ - исходники для штатного компилятора
МАДЛЕН.  Собираются они в три шага, каждый из которых берёт
предыдущий результат:

1. **имена меток** - метки разбора dtran названы номерами слов
   (`*0032B`); им даются осмысленные имена по содержанию помеченного
   блока (tools/siprod_labels.py): вызов внешней подпрограммы,
   обращение к общему блоку, работа с переменной модуля, возврат по
   М15, цикл.  Ручные имена (LABEL_NAMES) выигрывают - ими названы
   ветви разбора *-команд у SPAUD и вызовы обработчиков у SCHEMA;
2. **шапка и пояснения к меткам** - назначение модуля и смысл его
   процедур (tools/siprod_notes.py);
3. **пояснения к командам** - к каждой команде переносится комментарий
   из текста БЕМШ: что делает операция и что означает операнд.

Тексты, однажды наполненные, не перезаписываются: без --force
инструмент собирает только те модули, где пояснений ещё нет.  Каталог
madlen-gen/ (результат разбора) не трогается, поэтому обычная
пересборка (`make madlen`) не затирает правку текстов.

Использование:
    tools/siprod_madlen_build.py             # собрать madlen/
    tools/siprod_madlen_build.py --force     # пересобрать заново
    tools/siprod_madlen_build.py --check     # только проверить
"""

from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from siprod_bemsh import parse_be                                 # noqa: E402
from siprod_labels import module_table                          # noqa: E402
from siprod_lib import Library                                  # noqa: E402
from siprod_notes import LABEL_NOTES, MODULE_NOTES              # noqa: E402

GEN = os.path.join(ROOT, "madlen-gen")
DST = os.path.join(ROOT, "madlen")
TXT = os.path.join(ROOT, "text")
IMAGE = os.path.join(ROOT, "siprod.bin")

LABEL_RE = re.compile(r"\*([0-7]+)B")
# объявления символов и данные - не команды
DECL = re.compile(r"^[^,]*[:,]\s*(LC|SUBP|LP|EQU|NAME)\b")
DATA = re.compile(r"^[^,]*[:,]\s*(ISO|INT|LOG|OCT|BSS|HEX|BIN)\b")


# ---------------------------------------------------------------- имена

def rename_labels(text, table):
    """Переименовать метки *NNNB в тексте МАДЛЕН."""
    mapping = {"%04o" % word: nm for word, nm in table.items()}

    def repl(mo):
        return mapping.get(mo.group(1), mo.group(0))

    return LABEL_RE.sub(repl, text)


# Поле регистра команды: у dtran оно восьмеричное с признаком `B`
# (`11B,XTA,`), а после метки - десятичное (`МЕТКА:11,XTA,`).
REG_OCT = re.compile(r"(?m)^(\s*)((?:[^\s:,]+:)?)([0-7]+)B,")
REG_DEC = re.compile(r"(?m)^(\s*)((?:[^\s:,]+:)?)([0-9]+),")


def register_names(text):
    """Регистры - именами: `11B,XTA,` -> `M11,XTA,`.

    В МАДЛЕН регистр - обычный символ, поэтому в начале модуля
    объявляются константы `M11:,EQU,11B` (значение - код регистра), а
    в командах регистр пишется именем: `M11,XTA,`.  Имя регистра -
    его код в восьмеричной записи (M11 = 11B = 9, M13 = 13B = 11).
    """
    used = set()
    for mo in REG_OCT.finditer(text):
        used.add(int(mo.group(3), 8))
    for mo in REG_DEC.finditer(text):
        used.add(int(mo.group(3)))
    text = REG_OCT.sub(
        lambda mo: "%s%sM%o," % (mo.group(1), mo.group(2),
                                 int(mo.group(3), 8)), text)
    text = REG_DEC.sub(
        lambda mo: "%s%sM%o," % (mo.group(1), mo.group(2),
                                 int(mo.group(3))), text)
    return text, used


def register_defs(used):
    """Объявления регистров модуля: `M11:,EQU,11B`."""
    return [" M%o:,EQU,%oB" % (r, r) for r in sorted(used)]


def insert_defs(text, defs):
    """Вставить объявления после объявления модуля (`:,NAME,`)."""
    if not defs:
        return text
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if ",NAME," in line:
            return "\n".join(lines[:i + 1] + defs + lines[i + 1:])
    return text


def split_procedures(text):
    """Разделить текст на процедуры - по безусловным переходам.

    В текстах БЕМШ каждая процедура заканчивается безусловным
    переходом и отделяется строкой `*`; в МАДЛЕН та же граница -
    команда `UJ`, а разделителем служит пустая строка комментария.
    """
    out = []
    for line in text.splitlines():
        out.append(line)
        st = line.strip()
        if "," in st:
            op = st.split(",")[1].strip().upper()
            if op == "UJ":
                out.append("C")
    return "\n".join(out)


def rename_equ(text, names):
    """Переименовать служебные имена GAK/n, GAL/n и т.п.

    Разборщик dtran даёт записям таблицы символов, для которых не
    нашлось имени, служебное имя вида GAK/5 (G, две буквы номера
    записи, /, номер).  На самом деле такая запись - ссылка «символ +
    смещение», и её настоящее имя уже известно (например, NDAB1), -
    значит, служебное имя можно заменить.  Переименуются и объявления,
    и ссылки на них - иначе ссылка останется на несуществующее имя.
    """
    for old, new in names.items():
        text = re.sub(r"(?<![\w/])%s(?![\w/])" % re.escape(old), new, text)
    return text


def equ_names(lib, module):
    """Служебные имена G??/n -> настоящие имена символов.

    Имя служебной записи строится разборщиком так: 'G', две буквы
    номера записи, '/', номер.  Номер записи закодирован так:
    буквы - это (номер / 128) и (номер / 8 % 16), цифра - номер % 8.
    """
    from siprod_dis import symbol_table
    ext, _labels, symtab = symbol_table(lib, module)
    out = {}
    for i, e in enumerate(symtab):
        if not e or e[0] != "ref":
            continue
        base = ext.get(e[1])
        real = ext.get(i)
        if base is None or real is None or real == base:
            continue
        out[gak_name(i)] = real
    return out


def gak_name(i):
    """Служебное имя записи таблицы символов (как у разборщика dtran)."""
    return "G%s%s/%d" % (chr(ord("A") + i // 128),
                         chr(ord("K") + i // 8 % 16), i % 8)


# ---------------------------------------------------------------- шапка

def header(module):
    """Шапка текста БЕМШ - строки комментария МАДЛЕН.

    Шапка - это строки между первой и второй рамками из звёздочек
    (до раздела «СИМВОЛЫ МОДУЛЯ»).
    """
    path = os.path.join(TXT, module.replace("*", "#") + ".be")
    if not os.path.exists(path):
        return []
    out = []
    frames = 0
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if line.startswith("***"):
            frames += 1
            if frames >= 2:
                break
            continue
        if line.startswith("*"):
            out.append(line[1:].strip())
        elif frames == 1 and not out:
            continue
        elif frames == 1 and line.strip():
            out.append(line.strip())
    return out


def module_notes(module):
    """Пояснения к модулю: строки текста.

    В шапку переносятся сведения из текста БЕМШ: назначение модуля,
    вход, выход (куда модуль возвращает управление и через какой
    регистр), внешние символы, регистры.  Ручные пояснения
    (MODULE_NOTES) идут после них и не дублируют шапку.
    """
    # вся шапка целиком: источник, длина, вход, выход, внешние символы,
    # регистры - всё это нужно читателю текста
    out = list(header(module))
    for l in MODULE_NOTES.get(module, []):
        if l not in out:
            out.append(l)
    return out


def label_notes(lib, module, table):
    """Пояснения к меткам: имя метки -> текст.

    Ключ LABEL_NOTES - смещение команды от начала модуля, а метка
    находится по номеру слова (в слове две команды).
    """
    notes = LABEL_NOTES.get(module, {})
    out = {}
    for cmd, note in notes.items():
        name = table.get(cmd // 2)
        if name:
            out[name] = note
    return out


# ------------------------------------------------------- пояснения к командам

def be_comments(module):
    """Пояснения к командам модуля: номер команды -> текст.

    Номер команды - как в разборе БЕМШ: номер слова и половина слова.
    """
    path = os.path.join(TXT, module.replace("*", "#") + ".be")
    if not os.path.exists(path):
        return {}
    _locsyms, _labels, instrs, _data = parse_be(path)
    out = {}
    for num, _instr, op, _lab in instrs:
        text = op.strip()
        if not text:
            continue
        # в тексте БЕМШ операнд и комментарий разделены запятой
        if "," in text:
            text = text.split(",", 1)[1].strip()
        if text:
            out[num] = text
    return out


def madlen_commands(lines, lib, module):
    """Для каждой строки МАДЛЕН - номер команды (None - не команда).

    Разборщик dtran печатает команду на строку, но команды с
    признаком «вторая половина слова не инструкция» (02200000) не
    печатает, поэтому номер команды накапливает пропуски.
    """
    s, h = lib.objects[module]
    rows = []
    word = 0
    half = 0
    for line in lines:
        st = line.strip()
        if not st or st.startswith("C"):
            rows.append(None)
            continue
        if DECL.match(st) or DATA.match(st):
            rows.append(None)
            continue
        if word >= h["cmd"]:
            rows.append(None)
            continue
        w = lib.words[s + 3 + word]
        rows.append(word * 2 + half)
        half += 1
        if half == 2:
            half = 0
            word += 1
    return rows


# ---------------------------------------------------------------- сборка

def build(lib, module):
    """Текст МАДЛЕН: имена меток, шапка, пояснения."""
    gen = os.path.join(GEN, module.replace("*", "#") + ".madlen")
    if not os.path.exists(gen):
        return None
    table = module_table(lib, module)
    text = rename_labels(open(gen, encoding="utf-8").read(), table)
    text = rename_equ(text, equ_names(lib, module))
    text, used = register_names(text)
    text = insert_defs(text, register_defs(used))
    lines = text.splitlines()

    # шапка и пояснения к меткам
    notes = label_notes(lib, module, table)
    head = [comment(l) for l in module_notes(module)]
    if head:
        head.append(comment(""))
    out = list(head)
    for line in lines:
        m = re.match(r"\s*([A-Za-zА-ЯЁ][A-Za-zА-ЯЁ0-9_]*):", line)
        if m and m.group(1) in notes:
            out.append(comment(" " + notes[m.group(1)]))
        out.append(line)

    # пояснения к командам: комментарий отделяется точкой
    comments = be_comments(module)
    if comments:
        rows = madlen_commands(out, lib, module)
        final = []
        for line, num in zip(out, rows):
            note = comments.get(num) if num is not None else None
            if not note:
                final.append(line)
                continue
            final.append(line.rstrip() + "." + note)
        out = final
    # процедуры разделены по безусловным переходам
    return split_procedures("\n".join(out)) + "\n"


def comment(text):
    """Строка комментария МАДЛЕН."""
    return "C" + text


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
    done = 0
    for f in sorted(os.listdir(GEN) if os.path.isdir(GEN) else []):
        if not f.endswith(".madlen"):
            continue
        module = f[:-7].replace("#", "*")
        if args.modules and module not in args.modules:
            continue
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
                print("   без шапки: %s" % f)
        print("без шапки: %d" % bad)
    return 0


if __name__ == "__main__":
    sys.exit(main())
