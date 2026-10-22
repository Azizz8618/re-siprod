#!/usr/bin/env python3
"""Данные модулей СИПРОДа: что объявлено и на что ссылается код.

Разбор dtran печатает раздел данных модуля: объявления констант
(`ИМЯ:,INT,значение`) и переменных (`ИМЯ:,BSS,размер`).  Часть
объявлений идёт без имени - это продолжение раздела, и по тексту
непонятно, что это за данные.

Инструмент показывает по каждому модулю:
  * что объявлено в разделе данных (с номерами слов);
  * на какие слова данных ссылается код модуля (абсолютный адрес);
  * какие ячейки кадра (М7) использует модуль - через них адресуются
    его переменные;
  * какие внешние символы модуля на него ссылаются.

Использование:
    tools/siprod_data.py [МОДУЛЬ ...]
"""

from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from siprod_be import decode, info, operand_text          # noqa: E402
from siprod_lib import Library                          # noqa: E402

GEN = os.path.join(ROOT, "madlen-gen")
IMAGE = os.path.join(ROOT, "siprod.bin")

# строка данных dtran: "ИМЯ:,ТИП,ЗНАЧЕНИЕ" либо ",ТИП,ЗНАЧЕНИЕ"
DATA_RE = re.compile(
    r"^\s*(?:([A-Za-zА-ЯЁ*][A-Za-zА-ЯЁ0-9_+*]*)?:)?,?"
    r"(BSS|ISO|INT|LOG|OCT|HEX|BIN|SET|LONG)(?:,(.*))?$")
# операнд-адрес: число (с необязательным B) или выражение
OPER_RE = re.compile(r"^(.+)$")


def data_items(module):
    """Объявления раздела данных модуля: (слово, имя, тип, значение).

    Разбор dtran печатает данные в конце модуля; номер слова стоит
    в метке «*0167B», у продолжений (без метки) номер следующий.
    """
    path = os.path.join(GEN, module.replace("*", "#") + ".madlen")
    if not os.path.exists(path):
        return []
    raw = []                      # (слово или None, имя, тип, значение)
    for line in open(path, encoding="utf-8"):
        st = line.strip()
        if st.startswith(",DATA"):
            break                         # конец раздела данных
        m = DATA_RE.match(st)
        if not m:
            continue
        name, kind, val = m.group(1), m.group(2), m.group(3)
        lm = re.match(r"^\*([0-7]+)B", st)
        word = int(lm.group(1), 8) if lm else None
        raw.append((word, name, kind, (val or "").strip()))
    # слова без номера (продолжение предыдущей декларации) занимают
    # слова после неё; безымянные декларации в начале раздела стоят
    # перед первой помеченной - занимают слова перед ней
    first = next((i for i, it in enumerate(raw) if it[0] is not None), None)
    if first:
        w = raw[first][0] - first
        for i in range(first):
            name, kind, val = raw[i][1], raw[i][2], raw[i][3]
            raw[i] = (w, name, kind, val)
            w += 1
    out = []
    word = None
    for w, name, kind, val in raw:
        if w is not None:
            word = w
        elif word is None:
            continue                  # нет номера - слово неизвестно
        out.append((word, name, kind, val))
        word += 1
    return out


def commands(module):
    """Команды модуля в разборе dtran: (номер, регистр, операция, операнд).

    Операнд берётся из самого разбора: там он записан так, как его
    понимает компилятор МАДЛЕН («*0012B» - слово, «К0» - символ).
    Регистр стоит перед операцией: «M7,ATX,10B» - запись в слот 10
    кадра, адресуемого регистром М7.
    """
    path = os.path.join(GEN, module.replace("*", "#") + ".madlen")
    out = []
    if not os.path.exists(path):
        return out
    num = 0
    for line in open(path, encoding="utf-8"):
        st = line.strip()
        if not st or st.startswith("C"):
            continue
        head = st.split(",", 1)[0]
        # метка отбрасывается: "МЕТКА:11" -> "11"
        reg = head.split(":")[-1].strip()
        parts = st.split(",")
        if len(parts) < 2:
            continue
        op = parts[1].strip()
        if not op or not op[0].isalpha():
            continue                      # объявление, а не команда
        operand = parts[2].strip() if len(parts) > 2 else ""
        out.append((num, reg, op, operand))
        num += 1
    return out


def references(lib, module):
    """Ссылки кода модуля: слова данных и ячейки кадра.

    Ссылка на данные может быть числом (абсолютный адрес), меткой
    dtran («*0012B») или именем символа («ПАРАМЕТР+2»).
    """
    from siprod_labels import module_table
    ext, labels, exits, insns = info(lib, module)
    s, h = lib.objects[module]
    ncmd = h["cmd"]
    data_words = {}
    for word, name, kind, val in data_items(module):
        if word is not None:
            data_words[word] = (name, kind, val)
    byname = {}
    for word, nm in module_table(lib, module).items():
        byname.setdefault(nm, word)
    abs_refs = {}
    frame = {}
    for num, reg, op, operand in commands(module):
        if reg == "7":              # регистр М7 - указатель кадра
            m = re.match(r"^(-?\d+)(?:B)?$", operand)
            if m:
                frame.setdefault(int(m.group(1)), []).append((num, op))
            continue
        m = re.match(r"^\*([0-7]+)B(?:\+(\d+))?$", operand)
        if m:
            val = int(m.group(1), 8) + int(m.group(2) or 0)
            if val in data_words:
                abs_refs.setdefault(val, []).append((num, op))
            continue
        m = re.match(r"^(\d+)(?:B)?$", operand)
        if m:
            val = int(m.group(1))
            if val in data_words:
                abs_refs.setdefault(val, []).append((num, op))
            continue
        m = re.match(r"^([A-Za-zА-ЯЁ][A-Za-zА-ЯЁ0-9_]*)(?:\+(\d+))?$", operand)
        if m:
            base, add = m.group(1), int(m.group(2) or 0)
            if base in byname:
                val = byname[base] + add
                if val in data_words:
                    abs_refs.setdefault(val, []).append((num, op))
    return data_words, abs_refs, frame


def main():
    lib = Library(IMAGE)
    modules = sys.argv[1:] or sorted(lib.objects)
    for module in modules:
        if module not in lib.objects:
            print("нет модуля: %s" % module)
            continue
        data, abs_refs, frame = references(lib, module)
        ext, labels, exits, insns = info(lib, module)
        s, h = lib.objects[module]
        ncmd = h["cmd"]
        print("=== %s: команд %d, данных %d" % (module, ncmd, len(data)))
        for word in sorted(data):
            name, kind, val = data[word]
            refs = abs_refs.get(word, [])
            mark = "используется" if refs else "НЕ ИСПОЛЬЗУЕТСЯ"
            print("   слово %4d (0o%-5o) %-6s %-24s %s"
                  % (word, word, kind, (val or "")[:24], mark))
            for off, instr in refs[:4]:
                print("        команда %4d: %s" % (off, instr))
        if frame:
            print("   ячейки кадра: %s"
                  % ", ".join(str(k) for k in sorted(frame)))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
