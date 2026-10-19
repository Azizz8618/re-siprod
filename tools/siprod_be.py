#!/usr/bin/env python3
"""Генерация текстов БЕМШ модулей СИПРОДа с комментариями.

Правила оформления - как в проекте re-dispak (ОС ДИСПАК):

  * комментарий в строке начинается с запятой, отступ до запятой - не
    менее двух пробелов; комментарий начинается с 40-го столбца, если
    строка короче, иначе ставится сразу за кодом;
  * длина строки комментария - не более 55 символов, перенос - звёздочкой
    в начале следующей строки;
  * полнострочный комментарий начинается с `*`;
  * имена меток - не более 6 знаков, начинаются с буквы;
  * шапка модуля - блок `*****` с назначением, связями и регистрами.

Тексты собираются из разобранных команд модуля (`tools/siprod_asm.py`),
имена символов - из таблицы символов модуля (`tools/siprod_dis.py`).

Использование:
    tools/siprod_be.py                # все модули -> src/
    tools/siprod_be.py SCAN SPAUD     # только указанные
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from siprod_asm import decode  # noqa: E402
from siprod_dis import (LOC_TAG, STRUCT_BIT, SYM_TAG, is_struct,  # noqa: E402
                         local_refs, sanitize, symbol_table, unique_name)
from siprod_notes import LABEL_NOTES, MODULE_NOTES  # noqa: E402

SYM_MARK = "СИМВОЛЫ МОДУЛЯ"
LOCAL_MARK = "ЛОКАЛЬНЫЕ СИМВОЛЫ"
from siprod_lib import Library  # noqa: E402

COL_COMMENT = 40       # столбец начала комментария
MAX_COMMENT = 55       # предел длины строки комментария

# КОП -> (МАДЛЕН, описание); таблица rukava.be (см. re-dispak)
OPCODE_TABLE = {
    "ЗП": ("ATX", "запись СМ по адресу"),
    "ЗПМ": ("STX", "запись магазинная"),
    "РЕГ": ("MOD", "обращение к спец.регистрам"),
    "СЧМ": ("XTS", "магазинная запись, затем СЧ"),
    "СЛ": ("A+X", "сложение"),
    "ВЧ": ("A-X", "вычитание"),
    "ВЧОБ": ("X-A", "вычитание обратное"),
    "ВЧАБ": ("AMX", "вычитание абсолютных величин"),
    "СЧ": ("XTA", "считывание"),
    "И": ("AAX", "логическое И"),
    "НТЖ": ("AEX", "исключающее ИЛИ"),
    "СЛЦ": ("ARX", "циклическое сложение"),
    "ЗНАК": ("AVX", "изменение знака"),
    "ИЛИ": ("AOX", "логическое ИЛИ"),
    "ДЕЛ": ("A/X", "деление"),
    "УМН": ("A*X", "умножение"),
    "СБР": ("APX", "сборка битов"),
    "РЗБ": ("AUX", "разборка битов"),
    "ЧЕД": ("ACX", "число единиц"),
    "НЕД": ("ANX", "номер старшей единицы"),
    "СЛП": ("E+X", "сложение порядков"),
    "ВЧП": ("E-X", "вычитание порядков"),
    "СД": ("ASX", "сдвиг"),
    "РЖ": ("XTR", "установка РЖ"),
    "СЧРЖ": ("RTE", "считывание РЖ на СМ"),
    "СЧМР": ("YTA", "передача РМР на СМ"),
    "УВВ": ("EXT", "управление ВВ (привил.)"),
    "СЛПА": ("E+N", "сложение порядка с константой"),
    "ВЧПА": ("E-N", "вычитание константы из порядка"),
    "СДА": ("ASN", "сдвиг по адресу"),
    "РЖА": ("NTR", "установка РЖ по адресу"),
    "УИ": ("ATI", "установка индекс-регистра"),
    "УИМ": ("STI", "УИ + магазинное считывание"),
    "СЧИ": ("ITA", "считывание индекс-регистра"),
    "СЧИМ": ("ITS", "магазинная запись + СЧИ"),
    "УИИ": ("MTJ", "передача индекс-регистра"),
    "СЛИ": ("J+M", "сложение индекс-регистров"),
    "МОДА": ("UTC", "модификация адреса"),
    "МОД": ("WTC", "модификация адреса по коду"),
    "УИА": ("VTM", "установка ИР по адресу"),
    "СЛИА": ("UTM", "сложение ИР с адресом"),
    "ПО": ("UZA", "условный переход по нулю"),
    "ПЕ": ("UIA", "условный переход по единице"),
    "ПБ": ("UJ", "безусловный переход"),
    "ПВ": ("VJM", "переход с возвратом"),
    "ВЫПР": ("IJ", "возврат из прерывания"),
    "СТОП": ("33", "останов"),
    "ПИО": ("VZM", "переход по ИР=0"),
    "ПИНО": ("VIM", "переход по ИР≠0"),
    "ЦИКЛ": ("VLM", "конец цикла"),
}


def ref_name(half, ext, labels):
    """Имя символа для перемещаемого адреса (None - адрес не перемещаемый).

    Адресное поле (15 бит) помечено битами 14..12: 4 - локальная метка
    (смещение в командах от начала модуля), 7 - внешний символ (номер
    записи в таблице символов).
    """
    if not is_struct(half):
        return None
    value = half & 0o77777
    tag = (value >> 12) & 7
    if tag == SYM_TAG:
        index = value & 0o3777
        return ext.get(index, "СИМ%o" % index)
    if tag == LOC_TAG:
        off = value & 0o7777
        return labels.get(off, "*%04oB" % off)
    return None


def addr_text(value, name, entry):
    """Адрес в синтаксисе БЕМШ ('177', 177, 0)."""
    if name:
        return name
    if value == 0:
        return "0"
    if value < 0o100:
        return "%d" % value
    if value >= 0o77700:
        return "%d" % (value - 0o100000)
    return "'%o'" % value


def operand_text(dec, ext, labels, entry):
    """Операнд команды в синтаксисе БЕМШ."""
    kind = dec["kind"]
    reg = dec["reg"]
    raw = dec["raw"]
    if kind == "reg1":
        # младшие 5 разрядов - регистр, старшие - индексный регистр
        s = "М%o" % (raw & 0o37) if raw & 0o37 else ""
    elif kind in ("imm", "immex"):
        s = "'%o'" % dec["arg"] if dec["arg"] else ""
    elif kind == "imm64":
        v = dec["arg"] & 0o177
        s = "64" + ("%+d" % (v - 64) if v != 64 else "")
    elif kind == "imm2":
        s = "%d" % dec["arg"]
    else:
        name = ref_name(raw, ext, labels)
        s = addr_text(dec["arg"], name, entry)
    if reg:
        s += "(М%o)" % reg
    return s


def gen_comment(instr, op, ext):
    """Комментарий к команде: описание операции и операнда."""
    i = instr.upper().strip()
    o = op.strip()
    desc = OPCODE_TABLE.get(i)
    if desc is None:
        return None
    if i == "СЧ":
        if not o:
            return "загрузка вершины стека -> СМ"
        if o.startswith("(М"):
            return "СМ := (М%s) [косвенно]" % o[2:o.index(")")] \
                if ")" in o else "СМ := (Мx) [косв.]"
        return "СМ := %s" % o[:24]
    if i == "ЗП":
        return "(адрес) := СМ" if not o else "%s := СМ" % o.split("(")[0][:24]
    if i == "СЧИ":
        m = re.search(r"М(\d+)", o)
        return "СМ := М%s" % m.group(1) if m else "СМ := ИР"
    if i == "УИ":
        m = re.search(r"М(\d+)", o)
        return "М%s := СМ" % m.group(1) if m else "ИР := СМ"
    if i == "УИИ":
        ms = re.findall(r"М(\d+)", o)
        return "М%s := М%s" % (ms[0], ms[1]) if len(ms) >= 2 else "копия ИР"
    if i == "УИА":
        m = re.search(r"\(М(\d+)\)", o)
        val = o.split("(")[0].strip() or "0"
        return "М%s := %s" % (m.group(1), val[:18]) if m else "ИР := %s" % val[:18]
    if i == "СЛИА":
        m = re.search(r"\(М(\d+)\)", o)
        val = o.split("(")[0].strip() or "0"
        sign = "+" if not val.startswith("-") else ""
        return "М%s %s= %s" % (m.group(1), sign, val[:12]) if m \
            else "ИР += %s" % val[:12]
    if i == "СЛИ":
        ms = re.findall(r"М(\d+)", o)
        return "М%s += М%s" % (ms[0], ms[1]) if len(ms) >= 2 else "сложение ИР"
    if i in ("СЛ", "СЛЦ"):
        tail = " [цикли.]" if i == "СЛЦ" else ""
        return ("СМ += %s" % o[:20] + tail) if o else "СМ += (адрес)" + tail
    if i == "ВЧ":
        return "СМ -= %s" % o[:20] if o else "СМ -= (адрес)"
    if i == "ВЧОБ":
        return "СМ := (адрес) - СМ"
    if i == "ВЧАБ":
        return "СМ -= |адрес|"
    if i == "ЗНАК":
        return "СМ := -СМ (инверсия знака)"
    if i == "И":
        return "СМ &= %s" % o[:18] if o else "СМ &= (адрес)"
    if i == "ИЛИ":
        return "СМ |= %s" % o[:18] if o else "СМ |= (адрес)"
    if i == "НТЖ":
        return "СМ ^= %s" % o[:18] if o else "СМ ^= (адрес)"
    if i == "ДЕЛ":
        return "СМ /= %s" % o[:15] if o else "деление"
    if i == "УМН":
        return "СМ *= %s" % o[:15] if o else "умножение"
    if i == "СБР":
        return "сборка битов: %s" % o[:15] if o else "сборка битов"
    if i == "РЗБ":
        return "разборка битов: %s" % o[:15] if o else "разборка битов"
    if i == "ЧЕД":
        return "СМ := кол-во единиц в %s" % o[:12] if o else "число единиц"
    if i == "НЕД":
        return "СМ := № старш. единицы: %s" % o[:12] if o else "№ старш. единицы"
    if i == "СЛП":
        return "порядок += %s" % o[:15] if o else "сложение порядков"
    if i == "ВЧП":
        return "порядок -= %s" % o[:15] if o else "вычитание порядков"
    if i == "СД":
        m = re.search(r"М(\d+)", o)
        return "сдвиг СМ на М%s" % m.group(1) if m else "сдвиг СМ"
    if i == "СДА":
        if "64+" in o:
            return "сдвиг СМ вправо на %s" % o.split("+")[1][:4]
        if "64-" in o:
            return "сдвиг СМ влево на %s" % o.split("-", 1)[1][:4]
        return "сдвиг СМ на %s" % o[:10]
    if i == "РЖ":
        return "РЖ := СМ (режим ждущ.акк.)"
    if i == "РЖА":
        return "РЖ := %s" % o[:15] if o else "РЖ по адресу"
    if i == "СЧРЖ":
        return "СМ := РЖ (режим ждущ.акк.)"
    if i == "СЧМР":
        return "СМ := РМР (результат мантиссы)"
    if i == "СЛПА":
        return "порядок += %s" % o[:10] if o else "порядок += N"
    if i == "ВЧПА":
        return "порядок -= %s" % o[:10] if o else "порядок -= N"
    if i == "МОДА":
        return "мод.адрес +1: %s" % o[:12] if o else "мод.адрес +1"
    if i == "МОД":
        return "мод.адрес по коду: %s" % o[:12] if o else "мод.адрес по коду"
    if i == "ПО":
        return "если СМ=0 → %s" % o[:15] if o else "усл.пер. по 0"
    if i == "ПЕ":
        return "если СМ≠0 → %s" % o[:15] if o else "усл.пер. по 1"
    if i == "ПБ":
        if "(М" in o:
            m = re.search(r"\(М(\d+)\)", o)
            return "переход через М%s" % m.group(1) if m else "переход (косв.)"
        return "переход на %s" % o[:20]
    if i == "ПВ":
        if "(М" in o:
            m = re.search(r"\(М(\d+)\)", o)
            return "вызов через М%s" % m.group(1) if m else "вызов (косв.)"
        return "вызов %s" % o[:20]
    if i == "ПИО":
        return "если ИР=0 → %s" % o[:15] if o else "если ИР=0 → пропуск"
    if i == "ПИНО":
        return "если ИР≠0 → %s" % o[:15] if o else "если ИР≠0 → пропуск"
    if i == "ЦИКЛ":
        m = re.search(r"М(\d+)", o)
        return "М%s-- и если ≠0 → повтор" % m.group(1) if m else "конец цикла"
    if i == "ВЫПР":
        return "возврат из прерывания"
    if i == "СТОП":
        return "останов: %s" % o[:15] if o else "останов"
    if i == "СЧМ":
        return "магазин + СЧ: %s" % o[:15] if o else "магазин + считывание"
    if i == "ЗПМ":
        return "ЗП + магазин: %s" % o[:15] if o else "запись + магазин"
    if i == "УИМ":
        m = re.search(r"М(\d+)", o)
        return "М%s := СМ + стек" % m.group(1) if m else "УИ + магазин"
    if i == "СЧИМ":
        m = re.search(r"М(\d+)", o)
        return "стек := М%s, СМ := М%s" % (m.group(1), m.group(1)) if m \
            else "СЧИ + магазин"
    if i == "РЕГ":
        return "спец.регистр: %s" % o[:15] if o else "спец.регистр"
    if i == "УВВ":
        return "управление ВВ: %s" % o[:20] if o else "управление ВВ"
    return desc[1]


def with_comment(code, comment):
    """Добавить к строке кода комментарий (правила re-dispak).

    Комментарий начинается с 40-го столбца, если строка короче, иначе
    ставится сразу за кодом; длина строки - не более 78 символов.
    """
    if not comment:
        return code
    limit = 78
    if len(code) < COL_COMMENT:
        room = limit - COL_COMMENT - 1
        if len(comment) > room:
            comment = comment[:room]
        return code + " " * (COL_COMMENT - len(code)) + "," + comment
    room = limit - len(code) - 3
    if len(comment) > room:
        comment = comment[:room]
    return code + "  ," + comment


def block(lines):
    """Блок полнострочных комментариев."""
    out = [""]
    for ln in lines:
        out.append("* " + ln[:76] if ln else "*")
    out.append("*")
    return out


# назначение метки по роли первой команды блока, когда смысл оператора
# Фортрана определить нельзя
ROLE = {
    "СЧИМ": "PUSH", "СЧМ": "PUSH", "УИМ": "POP", "РЖА": "WAIT",
    "ПО": "CMP", "ПЕ": "CMP", "ПБ": "JMP", "УИА": "ADDR",
    "СЧ": "GET", "ЗП": "PUT", "ЗПМ": "PUT", "СЛИА": "INC", "СЛИ": "INC",
    "И": "AND", "ИЛИ": "OR", "НТЖ": "XOR", "ВЧ": "SUB", "ВЧОБ": "SUB",
    "СЛ": "ADD", "СЛЦ": "ADD", "МОДА": "FRAME", "МОД": "FRAME",
    "СЧИ": "GETR", "УИ": "SETR", "СЧРЖ": "GETW", "СЧМР": "MULR",
    "СДА": "SHL", "ЗНАК": "NEG", "ДЕЛ": "DIV", "УМН": "MUL",
    "СЧРЖ": "GETW", "РЖА": "WAIT", "Ц": "CYC",
}


AUTO_NAME = re.compile(r"^L[0-9]{3,4}$")


def exit_points(insns, ext, labels, module):
    """Точки выхода модуля: косвенные переходы через регистр.

    Компилятор Фортрана возвращает управление вызывающему прыжком
    по адресу, сохранённому в регистре (обычно М10 или М15).
    """
    res = []
    for off, half in insns:
        dec = decode(half)
        instr = (dec["name"] or "").upper()
        if instr != "ПБ":
            continue
        op = operand_text(dec, ext, labels, module)
        m = re.match(r"^0\(М(\d+)\)$", op)
        if m:
            res.append((off, "М%s" % m.group(1)))
        elif op == "0":
            # возврат по адресу из ячейки 0
            res.append((off, "ячейка 0"))
    return res


def call_sites(lib):
    """Кто кого вызывает: модуль -> список (вызывающий, метка вызова).

    Метка берётся ближайшая перед вызовом; вызов через оверлей
    относится к базовому модулю.
    """
    import json
    parent = {}
    try:
        with open("siprod.list") as f:
            for line in f:
                m = re.search(r"\(\s*([A-Z0-9*]+)\s*\)", line)
                if m:
                    parent[line.split()[0].strip("*")] = m.group(1)
    except OSError:
        pass
    # имя модуля -> приведённое имя
    mods = {}
    for name in lib.catalog:
        mods[sanitize(name)] = name
    sites = {}
    for name in sorted(lib.objects):
        s, h = lib.objects[name]
        ext, labels, _exits, _insns = info(lib, name)
        known = sorted(labels)
        for i in range(h["cmd"]):
            w = lib.words[s + 3 + i]
            for k, half in enumerate((w >> 24, w & 0xffffff)):
                dec = decode(half)
                if not dec["name"] or dec["name"].upper() != "ПВ":
                    continue
                if not is_struct(half):
                    continue
                v = half & 0o77777
                if (v >> 12) & 7 != SYM_TAG:
                    continue
                sym = ext.get(v & 0o3777)
                callee = mods.get(sym)
                if not callee:
                    continue
                while callee in parent:
                    callee = parent[callee]
                off = i * 2 + k
                # точка возврата - следующая метка вызывающего модуля
                after = [x for x in known if x > off]
                near = [x for x in known if x <= off]
                if after:
                    lab = labels[after[0]]
                elif near:
                    lab = labels[near[-1]] + "+1"
                else:
                    lab = "?"
                sites.setdefault(callee, []).append((name, lab, off))
    return sites


def subject(cand):
    """Имя, по которому можно назвать метку (автоматические имена не годятся)."""
    if not cand or AUTO_NAME.match(cand):
        return None
    return sanitize(cand)


def label_names(insns, ext, labels, module, cmdwords, constwords):
    """Осмысленные имена меток.

    Блок команд от метки до следующей метки разбирается на: вызов внешней
    подпрограммы, обращение к общему блоку (с номером элемента) или к
    локальной переменной модуля.  По этому метка и называется.  Ссылки на
    константы (раздел const) и на переменные (раздел bss) именуются по
    номеру слова: К<номер> и V<номер>.
    """
    items = []
    for off, half in insns:
        dec = decode(half)
        instr = (dec["name"] or "").upper()
        op = operand_text(dec, ext, labels, module)
        items.append((off, instr, op))
    used = set(ext.values())   # имена внешних символов заняты
    result = {}
    lastn = None            # последняя загрузка смещения в М7
    # обратные переходы - цели циклов
    loops = set()
    for i, (off, instr, op) in enumerate(items):
        if instr in ("ПБ", "ПО", "ПЕ") and op in labels:
            if labels[op] < off:
                loops.add(labels[op])
    for i, (off, instr, op) in enumerate(items):
        if instr == "СЧ":
            # смещение локальной переменной грузится в М7: "СЧ 9(М7)"
            m = re.match(r"^(\d+)\(М7\)$", op)
            if m:
                lastn = m.group(1)
        elif instr == "УИ" and op.startswith("М7"):
            lastn = None
        if off not in labels:
            continue
        # оператор Фортрана - от предыдущего безусловного перехода
        # до следующего; метка может стоять в середине оператора
        start = 0
        for k in range(i - 1, -1, -1):
            if items[k][1] in ("ПБ", "ПВ", "ВЫПР"):
                start = k + 1
                break
        j = i + 1
        while j < len(items) and items[j][1] not in ("ПБ", "ПВ", "ВЫПР"):
            j += 1
        calls, commons, locals = [], [], []
        for k in range(start, j):
            _, ins, o = items[k]
            if ins == "ПВ" and o:
                calls.append(o.split("(")[0])
            elif ins in ("МОДА", "МОД") and o:
                if o.split("(")[0] in (module, "0"):
                    locals.append(lastn)   # адрес своего кадра
                else:
                    commons.append(o.split("(")[0])
            elif ins in ("СЧ", "ЗП", "ЗПМ") and o:
                m = re.match(r"^(\d+)\(М7\)$", o)
                if m:
                    locals.append(m.group(1))
        base = None
        if off == 0:
            base = sanitize(module) or module
        else:
            for cand in calls:
                base = subject(cand)
                if base:
                    break
            if not base:
                for cand in commons:
                    base = subject(cand)
                    if base:
                        break
            if not base:
                for cand in locals:
                    base = subject("V%s" % cand if cand else "")
                    if base:
                        break
            if not base and off in loops:
                base = "LOOP"       # цель обратного перехода
            if not base:
                # роль команды: назначение метки по первой операции блока
                base = ROLE.get(instr)
            if not base:
                base = "L%04o" % off
        name = unique_name(base, used, fallback="L%04o" % off)
        used.add(name)
        result[off] = name
    # ссылки на константы и переменные (вне раздела команд) - по номеру
    # слова в соответствующем разделе
    for off in sorted(labels):
        if off in result or off < 2 * cmdwords:
            continue
        if off < 2 * (cmdwords + constwords):
            base = "К%d" % (off // 2 - cmdwords)
        else:
            base = "V%d" % (off // 2 - cmdwords - constwords)
        name = unique_name(base, used, fallback="L%04o" % off)
        used.add(name)
        result[off] = name
    return result


MODINFO = {}


def info(lib, name):
    """Сведения о модуле: имена меток, символы, выходы (с кэшем)."""
    if name in MODINFO:
        return MODINFO[name]
    s, h = lib.objects[name]
    code = lib.words[s + 3:s + 3 + h["cmd"]]
    ext, labels, symtab = symbol_table(lib, name)
    labels[0] = sanitize(name) or name
    for off in local_refs(code):
        labels.setdefault(off, "L%04o" % off)
    insns = []
    for i, w in enumerate(code):
        insns.append((i * 2, w >> 24))
        insns.append((i * 2 + 1, w & 0xffffff))
    names = label_names(insns, ext, labels, name, h["cmd"], h["const"])
    labels = names
    exits = exit_points(insns, ext, labels, name)
    MODINFO[name] = (ext, labels, exits, insns)
    return MODINFO[name]


def module_text(lib, name, loadmap):
    """Текст БЕМШ модуля."""
    s, h = lib.objects[name]
    code = lib.words[s + 3:s + 3 + h["cmd"]]
    ext, labels, symtab = symbol_table(lib, name)
    # начало модуля - его точка входа
    labels[0] = sanitize(name) or name
    # локальные метки, на которые ссылаются команды, но которые не названы
    # в таблице символов, получают автоматические имена
    for off in local_refs(code):
        labels.setdefault(off, "L%04o" % off)
    entry = name

    # команды модуля: в слове две, левая - старшие 24 бита
    insns = []
    for i, w in enumerate(code):
        insns.append((i * 2, w >> 24))
        insns.append((i * 2 + 1, w & 0xffffff))

    exits = exit_points(insns, ext, labels, name)
    regs = set()
    # внешние имена и смещения, с которыми на них ссылается модуль
    bases = []
    offsets = {}
    for i, e in enumerate(symtab):
        if not e:
            continue
        if e[0] in ("subp", "lc", "lp") and e[1]:
            nm = sanitize(e[1])
            if nm and nm not in bases:
                bases.append(nm)
        elif e[0] == "ref" and e[1] < len(symtab):
            base = symtab[e[1]]
            if base and base[0] in ("subp", "lc", "lp") and base[1] \
                    and e[2] != 0o77777:
                offsets.setdefault(sanitize(base[1]), set()).add(e[2])
    # осмысленные имена меток
    names = label_names(insns, ext, labels, name, h['cmd'], h['const'])
    labels = names
    lines = []
    for off, half in insns:
        dec = decode(half)
        instr = (dec["name"] or "???").upper()
        op = operand_text(dec, ext, labels, entry)
        for m in re.finditer(r"(?<![A-Za-zА-Яа-яЁё])М(\d+)", op):
            regs.add(int(m.group(1), 8))
        lbl = ""
        if off in labels and off != 0:
            lbl = labels[off]
        code_part = "%-9s%-7s%s" % (lbl, instr, op)
        comment = gen_comment(instr, op, ext)
        if comment:
            comment = comment[:MAX_COMMENT]
        note = LABEL_NOTES.get(name, {}).get(off) if off else None
        if note:
            lines.append("* " + note)
        lines.append(with_comment(code_part.rstrip(), comment))
        if instr == "ПБ":
            # конец базового блока - отделяем звёздочкой
            lines.append("*")
    return lines, bases, offsets, sorted(regs), h, ext, labels, exits


def wrap_head(prefix, items, width=76):
    """Перенос длинного перечня в шапке по строкам."""
    out = []
    line = prefix
    for it in items:
        if len(line) + len(it) + 2 > width and line != prefix:
            out.append(line)
            line = "*   " + it + ", "
        else:
            line += ("" if line.endswith(" ") else " ") + it + ", "
    out.append(line.rstrip(", "))
    return out


CALL_SITES = {}   # модуль -> список мест вызова


def write_module(lib, name, outdir, loadmap):
    lines, bases, offsets, regs, h, ext, labels, exits = module_text(lib, name, loadmap)
    sites = CALL_SITES
    s = lib.objects[name][0]
    addr = loadmap.get(name)
    head = []
    head.append("*" * 51)
    head.append("* %s - МОДУЛЬ СИПРОДА" % name)
    head.append("*   Источник: личная библиотека (PERSO, зона 2702,")
    head.append("*   том 2248), слово %d образа SIPROD.BIN" % s)
    head.append("*   Длина при загрузке: %d слов, %d команд"
                % (h["cmd"] + h["bss"] + h["const"], h["cmd"] * 2))
    if addr:
        head.append("*   Адрес загрузки: %s(8)" % addr)
    head.append("*   Вход: %s" % name)
    if exits or sites.get(name):
        items = []
        for caller, lab, off in sites.get(name, []):
            items.append("%s:%s" % (caller, lab))
        known = sorted(labels)
        for off, reg in exits:
            near = [x for x in known if x <= off]
            if near:
                items.append("%s (возврат через %s)" % (labels[near[-1]], reg))
        head.extend(wrap_head("*   Выход: ", items))
    else:
        head.append("*   Выход: нет (модуль не возвращает управление)")
    for note in MODULE_NOTES.get(name, []):
        head.append("*   " + note)
    if bases:
        head.extend(wrap_head("*   Внешние: ", bases))
    for b, offs in sorted(offsets.items()):
        head.extend(wrap_head("*   Смещения в %s: " % b,
                              [str(o) for o in sorted(offs)]))
    if regs:
        head.extend(wrap_head("*   Регистры: ",
                              ["М%o" % r for r in regs]))
    head.append("*" * 51)
    out = list(head)
    # таблица символов модуля - по ней сборщик находит внешние имена
    out.append("*** %s" % SYM_MARK)
    for num, nm in sorted(ext.items()):
        out.append("*   %03d %s" % (num, nm))
    out.append("*")
    # локальные символы вне раздела команд (ссылки на константы и
    # переменные) - сборщику нужны их смещения
    offs = [off for off in sorted(labels) if off >= 2 * h["cmd"]]
    if offs:
        out.append("* %s (имя - смещение):" % LOCAL_MARK)
        for off in offs:
            out.append("*   %-6s %o" % (labels[off], off))
        out.append("*")
    out.append("*** КОД МОДУЛЯ")
    out.append("*")
    note0 = LABEL_NOTES.get(name, {}).get(0)
    if note0:
        out.append("* " + note0)
    out.append("%-9s%-7s%s" % (labels.get(0, name), "СТАРТ", "0"))
    out.extend(lines)
    out.append("")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, name.replace("*", "#") + ".be")
    with open(path, "w") as f:
        f.write("\n".join(out) + "\n")
    return path


def load_addresses(path):
    """Адреса загрузки модулей из карты загрузки dispak."""
    res = {}
    if not os.path.exists(path):
        return res
    for line in open(path):
        for m in re.finditer(r"(\S+)\s+([CE])\s+(\d{5})", line):
            if m.group(1) not in res:
                res[m.group(1)] = m.group(3)
    return res


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    opts = [a for a in sys.argv[1:] if a.startswith("-")]
    path = "siprod.bin"
    if args and os.path.exists(args[0]):
        path = args.pop(0)
    outdir = "text"
    for o in opts:
        if o.startswith("--out="):
            outdir = o[6:]
    lib = Library(path)
    global CALL_SITES
    CALL_SITES = call_sites(lib)
    loadmap = load_addresses("tests/siprod/loadmap-dispak.txt")
    names = args if args else sorted(lib.objects)
    for name in names:
        if name not in lib.objects:
            print("нет модуля: %s" % name, file=sys.stderr)
            continue
        p = write_module(lib, name, outdir, loadmap)
        print("%-10s -> %s" % (name, p))


if __name__ == "__main__":
    main()
