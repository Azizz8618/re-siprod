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

from siprod_bemsh import OPS, parse_be                           # noqa: E402
from siprod_areas import AREA_SIZES                          # noqa: E402
from siprod_data_sections import (group_of, section_text,        # noqa: E402
                               KIND_NUM)
from siprod_labels import (AREA_NOTES, DATA_AREA_NAMES, module_table,   # noqa: E402
                        sanitize, unique)
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


# ------------------------------------------------------- массивы данных

# Объявление элемента массива: ИМЯ+Номер:,BSS,1
ARRAY_DECL = re.compile(
    r"^(\s*)([A-Za-zА-ЯЁ][A-Za-zА-ЯЁ0-9_]*)\+(\d+):,(BSS|ISO|INT|LOG|OCT|HEX|BIN)\b(.*)$")
# Ссылка на элемент массива в операнде
ARRAY_REF = re.compile(
    r"([A-Za-zА-ЯЁ][A-Za-zА-ЯЁ0-9_]*)\+(\d+)")


def merge_arrays(text):
    """Собрать объявления массивов: BASE+1..BASE+N -> BASE (размер N).

    Переменные и константы модуля, идущие подряд, - элементы одного
    массива.  Объявлять их по одному не нужно: достаточно одного
    объявления на весь массив (`ЯЧ_АДР:,BSS,3`), а элементы адресуются
    как `ЯЧ_АДР`, `ЯЧ_АДР+1`, `ЯЧ_АДР+2` (смещение в словах).

    Имена элементов сдвигаются на единицу: первый элемент массива
    становится его началом.
    """
    lines = text.splitlines()
    # группы: основание -> список номеров (по порядку объявлений)
    groups = {}
    for line in lines:
        m = ARRAY_DECL.match(line)
        if not m:
            continue
        base, num = m.group(2), int(m.group(3))
        groups.setdefault(base, []).append(num)
    # оставляем только группы с последовательными номерами
    groups = {b: ns for b, ns in groups.items()
              if len(ns) >= 2 and ns == list(range(ns[0], ns[0] + len(ns)))}
    if not groups:
        return text
    shift = {}
    for base, ns in groups.items():
        for i, num in enumerate(ns):
            shift[(base, num)] = i          # 0 - начало массива, 1, 2, ...
    # 1. объявления: первый элемент - начало массива, остальные убираем
    out = []
    skip = set()
    decl = set()
    for idx, line in enumerate(lines):
        if idx in skip:
            continue
        m = ARRAY_DECL.match(line)
        if not m:
            out.append(line)
            continue
        base, num = m.group(2), int(m.group(3))
        kind, rest = m.group(4), m.group(5)
        if base not in groups or (base, num) not in shift:
            out.append(line)
            continue
        decl.add(idx)
        pos = shift[(base, num)]
        if pos == 0:
            if kind == "BSS":
                # весь массив - одно объявление
                out.append("%s%s:,BSS,%d" % (m.group(1), base, len(groups[base])))
                skip.update(range(idx + 1, idx + len(groups[base])))
                decl.update(range(idx + 1, idx + len(groups[base])))
                continue
            out.append("%s%s:,%s%s" % (m.group(1), base, kind, rest))
            continue
        # объявление промежуточного элемента: имя со смещением
        out.append("%s%s+%d:,%s%s" % (m.group(1), base, pos, kind, rest))
    # 2. ссылки в операндах (объявления уже переименованы)
    final = []
    for idx, line in enumerate(out):
        if idx in decl:
            final.append(line)
            continue
        cut = line.find(".")
        code, sep, tail = (line, "", "") if cut < 0 else (line[:cut], ".", line[cut:])
        def repl(mo):
            base, num = mo.group(1), int(mo.group(2))
            if (base, num) in shift:
                pos = shift[(base, num)]
                return base if pos == 0 else "%s+%d" % (base, pos)
            return mo.group(0)
        final.append(ARRAY_REF.sub(repl, code) + sep + tail)
    return "\n".join(final)


# Объявление элемента внешнего массива: FOR1:,EQU,*FOR* +1
EQU_ARRAY = re.compile(
    r"^(\s*)([A-Za-zА-ЯЁ][A-Za-zА-ЯЁ0-9_]*):,EQU,(\S+)\s*\+\s*(\d+)\s*$")


def merge_equ_arrays(text):
    """Убрать объявления элементов внешнего массива.

    Внешний массив объявлен один раз (`*FOR* :,LC,8`), а его элементы
    перечислены как `FOR1:,EQU,*FOR* +1`.  По соглашению элемент
    адресуется смещением от начала массива (`*FOR*+1`), поэтому
    отдельные объявления не нужны.
    """
    lines = text.splitlines()
    repl = {}
    out = []
    for line in lines:
        m = EQU_ARRAY.match(line)
        if m:
            repl[m.group(2)] = "%s+%s" % (m.group(3), m.group(4))
            continue                       # объявление элемента не нужно
        out.append(line)
    if not repl:
        return text
    final = []
    for line in out:
        cut = line.find(".")
        code, sep, tail = (line, "", "") if cut < 0 else (line[:cut], ".", line[cut:])
        def sub(mo):
            return repl.get(mo.group(0), mo.group(0))
        final.append(re.sub(r"[A-Za-zА-ЯЁ][A-Za-zА-ЯЁ0-9_]*", sub, code) + sep + tail)
    return "\n".join(final)


# ------------------------------------------------------- имена данных

# Числительные для имён констант
NUMERALS = {
    0: "НОЛЬ", 1: "ЕДИНИЦА", 2: "ДВОЙКА", 3: "ТРОЙКА", 4: "ЧЕТЫРЬ",
    5: "ПЯТЬ", 6: "ШЕСТЬ", 7: "СЕМЬ", 8: "ВОСЕМЬ", 9: "ДЕВЯТЬ",
    10: "ДЕСЯТЬ", 11: "ОДИННАДЦАТЬ", 12: "ДВЕНАДЦАТЬ", 13: "ТРИНАДЦАТЬ",
    14: "ЧЕТЫРНАДЦАТЬ", 15: "ПЯТНАДЦАТЬ", 16: "ШЕСТНАДЦАТЬ",
    17: "СЕМНАДЦАТЬ", 18: "ВОСЕМНАДЦАТЬ", 19: "ДЕВЯТНАДЦАТЬ",
    20: "ДВАДЦАТЬ", 21: "ДВАДЦАТЬ_ОДИН", 22: "ДВАДЦАТЬ_ДВА",
    23: "ДВАДЦАТЬ_ТРИ", 24: "ДВАДЦАТЬ_ЧЕТЫРЕ", 25: "ДВАДЦАТЬ_ПЯТЬ",
    26: "ДВАДЦАТЬ_ШЕСТЬ", 27: "ДВАДЦАТЬ_СЕМЬ", 28: "ДВАДЦАТЬ_ВОСЕМЬ",
    29: "ДВАДЦАТЬ_ДЕВЯТЬ", 30: "ТРИДЦАТЬ", 32: "ТРИДЦАТЬ_ДВА",
    40: "СОРОК", 48: "СОРОК_ВОСЕМЬ", 50: "ПЯТЬДЕСЯТ",
    60: "ШЕСТЬДЕСЯТ", 64: "ШЕСТЬДЕСЯТ_ЧЕТЫРЕ", 80: "ВОСЕМЬДЕСЯТ",
    95: "ДЕВЯНОСТО_ПЯТЬ", 100: "СТО", 104: "СТО_ЧЕТЫРЕ",
    128: "СТО_ДВАДЦАТЬ_ВОСЕМЬ", 1400: "ТЫСЯЧА_ЧЕТЫРЕСТА",
    2400: "ДВЕ_ТЫСЯЧИ_ЧЕТЫРЕСТА", 4000: "ЧЕТЫРЕ_ТЫСЯЧИ",
}

# Строка данных в разборе dtran: ",ТИП,ЗНАЧЕНИЕ" либо "  :,ТИП,ЗНАЧЕНИЕ"
DATA_LINE = re.compile(
    r"^(\s*)(?:([A-Za-zА-ЯЁ*][A-Za-zА-ЯЁ0-9_+*]*)?:)?,?"
    r"(BSS|ISO|INT|LOG|OCT|HEX|BIN)(?:,(.*))?$")
# Имя, выданное по номеру слова, ничего не значит - заменяем его
GENERIC_DATA = re.compile(r"^(КОНСТАНТА|ПЕРЕМЕННАЯ)(_|\+)\d+$")


def value_name(kind, val, used):
    """Имя безымянного объявления данных - по его значению.

    Константа называется по числу, маска - по набору признаков, строка
    - по содержимому (пробелы, тире, точки и т.п.).
    """
    val = (val or "").strip()
    if kind == "INT":
        try:
            num = int(val.split(".")[0])
        except ValueError:
            num = None
        base = NUMERALS.get(
            num, "КОНСТАНТА_%s" % (num if num is not None else "?"))
    elif kind == "LOG":
        base = "МАСКА_%s" % (val.split(".")[0].strip() or "ПУСТАЯ")
    elif kind == "ISO":
        text = val.split(".")[0]
        m = re.search(r"\d+H(.*)$", text)     # у ISO-строки: 6H'текст'
        body = m.group(1) if m else text
        body = body.strip().strip("'")
        if not body.strip():
            base = "МАСКА_ПРОБЕЛОВ"
        elif set(body) == {"-"}:
            base = "МАСКА_ТИРЕ"
        elif set(body) == {"."}:
            base = "МАСКА_ТОЧЕК"
        elif set(body) == {"I"}:
            base = "МАСКА_ЗНАКА"
        else:
            clean = "".join(ch for ch in body.upper() if ch.isalnum())[:8]
            if body.startswith("*"):
                # командная строка СИПРОДа: *0STA, *RED, ...
                base = "КОМАНДА_%s" % (clean or "ЗВЕЗДА")
            else:
                base = "МАСКА_%s" % (clean or "ТЕКСТА")
    else:
        base = "%s_%s" % (kind, val.split(".")[0].strip() or "БЕЗ_ИМЕНИ")
    return unique(sanitize(base), used)


def be_data_names(module):
    """Имена данных модуля из текста БЕМШ: (константы, переменные).

    В тексте БЕМШ данные объявлены как `К0 КОНД В'...'` (константа)
    и `V0 ПАМ 1` (переменная).  В разборе dtran переменные идут
    блоком без имён, поэтому имена берём отсюда.
    """
    path = os.path.join(TXT, module.replace("*", "#") + ".be")
    consts, vars_ = [], []
    if not os.path.exists(path):
        return consts, vars_
    for line in open(path, encoding="utf-8"):
        m = re.match(r"^\s*([A-Za-zА-ЯЁ][A-Za-zА-ЯЁ0-9_]*)\s+(КОНД|ПАМ)\b", line)
        if not m:
            continue
        (consts if m.group(2) == "КОНД" else vars_).append(m.group(1))
    return consts, vars_


def int_runs(lines):
    """Серии подряд идущих числовых констант: индекс строки -> (начало, номер)."""
    runs = {}
    i = 0
    while i < len(lines):
        m = DATA_LINE.match(lines[i])
        if m and m.group(3) == "INT":
            j = i
            while j < len(lines):
                mm = DATA_LINE.match(lines[j])
                if not mm or mm.group(3) != "INT":
                    break
                j += 1
            if j - i >= 4:
                for k in range(i, j):
                    runs[k] = (i, k - i)
            i = j
            continue
        i += 1
    return runs


def int_run_purpose(module):
    """Назначение таблицы числовых констант модуля."""
    try:
        from siprod_data_sections import section_text
        return "ЧИСЛА: " + section_text(module, "ЧИСЛА")
    except Exception:
        return "ЧИСЛА: ТАБЛИЦА ЧИСЛОВЫХ КОДОВ МОДУЛЯ"


def name_data(text, module=""):
    """Дать имена объявлениям данных, которым имён нет.

    В разборе dtran продолжение раздела данных идёт без имени
    (`,INT,3`, `,BSS,5`) - такие данные в тексте выглядят анонимно.
    Имена даются по значению (константы), по содержимому (маски) и по
    именам из текста БЕМШ (переменные); блок BSS разбивается на
    отдельные переменные.
    """
    lines = text.splitlines()
    used = set()
    for line in lines:
        m = re.match(r"^\s*([A-Za-zА-ЯЁ][A-Za-zА-ЯЁ0-9_+]*):,", line)
        if m:
            used.add(m.group(1))
    _consts, varnames = be_data_names(module) if module else ([], [])
    out = []
    src = []              # номер исходной строки для каждой строки out
    nvar = 0
    narea = 0
    used_keys = set()
    seen_groups = set()
    renamed = {}                 # старое имя -> новое (для раздела SET)
    for sidx, line in enumerate(lines):
        m = DATA_LINE.match(line)
        if not m:
            out.append(line)
            src.append(sidx)
            continue
        indent, name0, kind = m.group(1), m.group(2), m.group(3)
        val = (m.group(4) or "").strip()
        if name0 and not GENERIC_DATA.match(name0):
            g = group_of(name0, kind, val)
            if g not in seen_groups:
                seen_groups.add(g)
                out.append(comment(" %s: %s" % (g, section_text(module, g))))
                src.append(-1)
            out.append(line)             # имя уже есть
            src.append(sidx)
            continue
        # имя по номеру слова (КОНСТАНТА_656) ничего не значит -
        # называем по значению
        if kind == "BSS":
            # блок неинициализированных данных - одна область
            try:
                count = int(val.split(".")[0])
            except ValueError:
                count = 1
            narea += 1
            # имя области подбирается по её размеру: отчёты считают
            # области иначе, чем сборщик
            base = None
            key = None
            for k, nm2 in DATA_AREA_NAMES.items():
                if not k.startswith(module + "#") or k in used_keys:
                    continue
                if AREA_SIZES.get(k) == count:
                    base, key = nm2, k
                    used_keys.add(k)
                    break
            if base is None:
                # размер области неизвестен - назначаем по порядку
                for k, nm2 in DATA_AREA_NAMES.items():
                    if not k.startswith(module + "#") or k in used_keys:
                        continue
                    base, key = nm2, k
                    used_keys.add(k)
                    break
            if base is None and count == 1 and nvar < len(varnames):
                base = varnames[nvar]      # имя из текста БЕМШ
            if base is None:
                base = "ОБЛАСТЬ_МОДУЛЯ"
            nm = unique(sanitize(base), used)
            used.add(nm)
            note = AREA_NOTES.get(key) if key else None
            if note:
                out.append(comment(" " + note))
                src.append(-1)
            if "ПЕРЕМЕННЫЕ" not in seen_groups:
                seen_groups.add("ПЕРЕМЕННЫЕ")
                out.append(comment(" %s: %s" % ("ПЕРЕМЕННЫЕ", section_text(module, "ПЕРЕМЕННЫЕ"))))
                src.append(-1)
            out.append("%s%s:,BSS,%d" % (indent, nm, count))
            src.append(sidx)
            if name0:
                renamed[name0] = nm
            nvar += count
            continue
        nm = value_name(kind, val, used)
        used.add(nm)
        g = group_of(nm, kind, val)
        if g not in seen_groups:
            seen_groups.add(g)
            out.append(comment(" %s: %s" % (g, section_text(module, g))))
            src.append(-1)
        out.append("%s%s:,%s,%s" % (indent, nm, kind, val))
        src.append(sidx)
        if name0:
            renamed[name0] = nm
    # серии числовых констант - элементы одной таблицы: имя по номеру
    # внутри серии, а перед серией - заголовок с её назначением
    runs = int_runs(lines)
    if runs:
        out2 = []
        kod = 0                       # нумерация элементов по модулю
        for idx, line in enumerate(out):
            run = runs.get(src[idx]) if idx < len(src) else None
            if run:
                start, pos = run
                if pos == 0 and KIND_NUM not in seen_groups:
                    out2.append(comment(" " + int_run_purpose(module)))
                m = re.match(r"^\s*([А-ЯЁA-Z_0-9]+):,INT,", line)
                if m:
                    kod += 1
                    new_name = unique(sanitize("КОД_%d" % kod), used)
                    renamed[m.group(1)] = new_name
                    line = re.sub(r"^\s*[А-ЯЁA-Z_0-9]+:",
                                 " %s:" % new_name, line)
            out2.append(line)
        out = out2
    if renamed:
        # старое имя -> новое: ссылки и в коде, и в разделе SET
        pat = re.compile("(?<![A-Za-zА-ЯЁ0-9_])(%s)(?![A-Za-zА-ЯЁ0-9_])"
                         % "|".join(re.escape(k)
                                   for k in sorted(renamed, key=len, reverse=True)))

        def repl(mo):
            return renamed[mo.group(1)]

        out = [pat.sub(repl, line) for line in out]
    return "\n".join(out)


# ------------------------------------------------------- выравнивание

# Колонка, в которой начинается пояснение команды
COMMENT_COLUMN = 40


def align_line(line, note):
    """Команда и её пояснение - в отдельных колонках.

    Пояснение отделяется точкой, как и принято в МАДЛЕН; перед точкой
    добавляется отступ до COMMENT_COLUMN, чтобы пояснения всех команд
    стояли на одной вертикали.
    """
    code = line.rstrip()
    if not note:
        return code
    if len(code) < COMMENT_COLUMN:
        code = code.ljust(COMMENT_COLUMN)
    return code + "." + note


# ------------------------------------------------------- пояснения к командам

# Соответствие мнемоник МАКРО-БЕМШ операциям МАДЛЕН (notes/registers.md).
BEM2MAD = {
    "МОДА": "UTC", "СЧ": "XTA", "РЖА": "NTR", "СЧИМ": "ITS",
    "ПБ": "UJ", "УИА": "VTM", "ЗП": "ATX", "ПВ": "VJM",
    "СЛ": "A+X", "НТЖ": "AEX", "ПО": "UZA", "ВЧ": "A-X",
    "УИМ": "STI", "ПЕ": "U1A", "МОД": "WTC", "ВЧОБ": "X-A",
    "УИИ": "MTJ", "ЗПМ": "STX", "СЛИА": "UTM", "УИ": "ATI",
    "ИЛИ": "AOX", "СЧМ": "XTS", "И": "AAX", "СДА": "ASN",
    "СЧИ": "ITA", "ПИО": "VZM", "ЦИКЛ": "VLM", "ПИНО": "V1M",
    "СЛИ": "AAX", "ЧЕД": "ACX", "СЧМР": "YTA", "СЛЦ": "ARX",
    "СД": "ASX", "ДЕЛ": "A/X", "УМН": "A*X", "ВЧПА": "E-N",
    "СЛПА": "E+N",
}


def be_commands(module):
    """Команды модуля из текста БЕМШ: (мнемоника, операнд, пояснение).

    Пояснение берётся из самого файла (часть строки после запятой) -
    разборщик parse_be отдаёт только операнд, а пояснение команды
    («СМ := смещение в буфере 0») в операнд не входит.

    Разбор строк повторяет правила parse_be: строка «СТАРТ», объявления
    «КОНД»/«ПАМ» и «ФИНИШ» командами не являются.  Псевдокоманда
    «МОДА 0» (сброс модификации) машинной команды не имеет - в коде её
    нет, поэтому она пропускается.
    """
    path = os.path.join(TXT, module.replace("*", "#") + ".be")
    if not os.path.exists(path):
        return []
    out = []
    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        if line.startswith("***") or line.startswith("*"):
            continue
        # пояснение - часть строки после запятой, перед ней 2+ пробелов
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
            mnemonic = p2[0].upper()
            operand = p2[1].strip() if len(p2) > 1 else ""
        else:
            mnemonic = first.upper()
            operand = rest
        if mnemonic == "МОДА" and operand.strip() == "0":
            continue                       # сброс модификации - не команда
        out.append((mnemonic, operand, comment))
    return out


def madlen_op(line):
    """Операция МАДЛЕН в строке (None, если строка не команда)."""
    st = line.strip()
    if not st or st.startswith("C"):
        return None
    if DECL.match(st) or DATA.match(st):
        return None
    parts = st.split(",")
    if len(parts) < 2:
        return None
    op = parts[1].strip()
    return op if op and op[0].isalpha() else None


def align_comments(lines, module):
    """Пояснения к командам МАДЛЕН: номер строки -> текст.

    Тексты БЕМШ и МАДЛЕН описывают один и тот же код, но не совпадают
    построчно: в БЕМШ есть псевдокоманды («МОДА 0» - сброс модификации),
    которых в машинном коде нет, поэтому разборщик dtran их не печатает.
    Команды сопоставляются по мнемонике операции, с пропуском псевдокоманд.
    """
    bem = be_commands(module)
    out = {}
    i = 0
    for idx, line in enumerate(lines):
        op = madlen_op(line)
        if op is None:
            continue
        while i < len(bem):
            mnemonic, _operand, _comment = bem[i]
            if BEM2MAD.get(mnemonic) == op:
                break
            i += 1                       # псевдокоманда - её нет в коде
        if i >= len(bem):
            break
        _mnemonic, _operand, comment = bem[i]
        if comment:
            out[idx] = comment
        i += 1
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
    text = merge_arrays(text)
    text = merge_equ_arrays(text)
    text = name_data(text, module)
    lines = text.splitlines()

    # пояснения к командам: комментарий отделяется точкой.
    # Пояснения сопоставляются с командами по мнемонике операции -
    # строки БЕМШ и МАДЛЕН не совпадают построчно (см. align_comments).
    comments = align_comments(lines, module)
    if comments:
        lines = [align_line(line, comments.get(idx))
                 for idx, line in enumerate(lines)]

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
