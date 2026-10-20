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
from siprod_dis import (LOC_TAG, STRUCT_BIT, SYM_TAG, abs_symbols,  # noqa: E402
                         is_struct, local_refs, sanitize, symbol_table,
                         unique_name)
from siprod_notes import LABEL_NOTES, MODULE_NOTES  # noqa: E402

SYM_MARK = "СИМВОЛЫ МОДУЛЯ"
LOCAL_MARK = "ЛОКАЛЬНЫЕ СИМВОЛЫ"
from siprod_lib import Library  # noqa: E402

COL_COMMENT = 40       # столбец начала комментария
MAX_COMMENT = 55       # предел длины строки комментария

# Назначение регистров М1..М17 (по разбору текстов модулей и команд
# эмулятора БЭСМ-6; подробно - notes/registers.md).
# Ключ - значение ВОСЬМЕРИЧНОГО номера регистра (М12 -> 0o12 = 10).
REG_ROLES = {
    0o1:  "индекс: база модуля",
    0o2:  "рабочий регистр",
    0o3:  "рабочий регистр",
    0o4:  "рабочий регистр",
    0o5:  "рабочий регистр",
    0o6:  "рабочий регистр",
    0o7:  "указатель кадра",
    0o10: "блок вызывающего",
    0o11: "буфер, счётчик",
    0o12: "магазин, кадр параметров ОС",
    0o13: "счётчик",
    0o14: "смещение в буфере",
    0o15: "адрес возврата",
    0o16: "модифицированный адрес",
    0o17: "контекст задачи",
}

# Слоты кадра 0..10 - общие для всех модулей (рабочая область задачи),
# выше - собственная область модуля.
FRAME_COMMON = 10


def ranges(nums):
    """Список чисел -> сжатый вид: 0-3, 7, 9-12."""
    out = []
    nums = sorted(set(nums))
    i = 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        if j - i >= 1:
            out.append("%d-%d" % (nums[i], nums[j]))
        else:
            out.append("%d" % nums[i])
        i = j + 1
    return ", ".join(out)


def dec_const(op):
    """Операнд для комментария: восьмеричные константы -> десятичные.

    В текстах числа без кавычек десятичные, в кавычках - восьмеричные
    (так в МАКРО-БЕМШ).  В комментарии приводим к десятичным, чтобы
    значение читалось однозначно: '4023' -> 2067.
    """
    def rep(m):
        return "%d(М%s)" % (int(m.group(1), 8), m.group(2))
    return re.sub(r"'([0-7]+)'\(М(\d+)\)", rep, op)


# значения вне рабочей области задачи (>= 2048 = 0o4000) - элементы
# каталога задачи Монитор-80 (CAT = PC+2048, см.
# monitor80-re/permanent/newsyste.asm)
OUTSIDE = 0o4000
CATALOG = 2048

# имена элементов каталога задачи, известные по исходникам Монитор-80
CAT_NAMES = {
    0:  "каталог томов",
    1:  "нулевое слово",
    2:  "каталог временной библиотеки",
    16: "таблица страниц",
    80: "LWW",
    81: "SAV",
    83: "SAV1",
}

# смысл смещения при регистре (ключ - восьмеричный номер регистра)
OFFSET_MEANING = {
    0o1:  "смещение в базе",
    0o7:  "слот кадра",
    0o10: "поле блока вызывающего",
    0o11: "смещение в буфере",
    0o12: "параметр вызова ОС",
    0o13: "смещение в буфере",
    0o14: "смещение в буфере",
    0o15: "смещение в магазине",
    0o16: "ячейка мод.адреса",
    0o17: "поле контекста",
}

# режимы ожидания аккумулятора (РЖ): разряды задают условия переходов
# и округление (см. ~/dispak/dispak/cu.c, set_mode)
RZH_MODES = {
    0o2:  "переходы по нулю, округление",
    0o3:  "переходы по нулю",
    0o6:  "обращение к ОС",
    0o7:  "исключение, нормализация",
    0o22: "переходы по знаку",
}


def op_meaning(op):
    """Смысл операнда-константы: слот, смещение, адрес.

    Возвращает None, если операнд - имя (ссылка на метку).
    """
    m = re.match(r"^(\d+)\(М(\d+)\)$", op)          # десятичное смещение
    if m:
        val, reg = int(m.group(1)), int(m.group(2), 8)
    else:
        m = re.match(r"^'([0-7]+)'\(М(\d+)\)$", op)   # восьмеричное смещение
        if not m:
            return None
        val, reg = int(m.group(1), 8), int(m.group(2), 8)
    if val >= OUTSIDE:
        n = val - CATALOG
        name = CAT_NAMES.get(n)
        if name:
            return "каталог задачи: %s" % name
        return "каталог задачи: элемент %d" % n
    return "%s %d" % (OFFSET_MEANING.get(reg, "смещение"), val)

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


def local_offset(half):
    """Смещение локальной метки (в словах) из адресного поля команды.

    None, если команда не ссылается на локальную метку.
    """
    if not is_struct(half):
        return None
    value = half & 0o77777
    if (value >> 12) & 7 != LOC_TAG:
        return None
    return value & 0o7777


def ref_name(half, ext, labels):
    """Имя символа для перемещаемого адреса (None - адрес не перемещаемый).

    Адресное поле (15 бит) помечено битами 14..12: 4 - локальная метка
    (смещение в словах от начала модуля), 7 - внешний символ (номер
    записи в таблице символов).  Смещение метки в словах, а словарь
    меток ключуется номером команды (= 2 * смещение).
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
        return labels.get(2 * off, "*%04oB" % off)
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


def gen_comment(instr, op, ext, mod=None):
    """Комментарий к команде: описание операции и операнда.

    mod - операнд предыдущей МОДА/МОД: адрес этой команды увеличивается
    на мод.адрес (регистр М16).
    """
    i = instr.upper().strip()
    o = op.strip()
    mean = op_meaning(o)         # смысл константы (None для имён)
    desc = OPCODE_TABLE.get(i)
    if desc is None:
        return None
    if i == "СДА":
        return None              # сдвиг по адресу: смысл не восстановлен
    # команда сразу после МОДА/МОД: её адрес увеличивается на мод.адрес
    if mod:
        kind, mop = mod
        mm = re.match(r"^(.*?)\(М(\d+)\)$", mop)
        base = mop if not mm else "%s+М%s" % (mm.group(1), mm.group(2))
        body = o.split("(")[0]
        if body == "0":
            if i == "ЗП":
                return "по адресу %s := СМ" % base
            if i == "ЗПМ":
                return "по адресу %s := СМ (в магазин)" % base
            if i == "СЧ":
                return "СМ := слово по адресу %s" % base
            if i == "СЧМ":
                return "в магазин; СМ := слово по адресу %s" % base
            if i == "СЛ":
                return "СМ += слово по адресу %s" % base
            if i == "ВЧ":
                return "СМ -= слово по адресу %s" % base
            if i == "ВЧОБ":
                return "СМ := слово по адресу %s - СМ" % base
            if i == "И":
                return "СМ &= слово по адресу %s" % base
            if i == "ИЛИ":
                return "СМ |= слово по адресу %s" % base
            if i == "НТЖ":
                return "СМ ^= слово по адресу %s" % base
            if i == "УИА":
                m = re.search(r"\(М(\d+)\)", o)
                if m:
                    if kind == "МОД":
                        return "М%s := код из %s" % (m.group(1), base)
                    return "М%s := адрес %s" % (m.group(1), base)
        if i == "ПБ" and body == "0":
            return "переход по адресу в мод.адресе"
    if i == "СЧ":
        if not o:
            return "загрузка вершины стека -> СМ"
        if o.startswith("(М"):
            return "СМ := (М%s) [косвенно]" % o[2:o.index(")")] \
                if ")" in o else "СМ := (Мx) [косв.]"
        return "СМ := %s" % (mean or o)[:40]
    if i == "ЗП":
        if not o:
            return "(адрес) := СМ"
        if o == "0":
            # адрес 0 - перемещаемый: адрес базы модуля
            return "по адресу 0 := СМ"
        m = re.match(r"^'?\d+'?\(М(\d+)\)$", o)
        if m:
            if mean:
                return "%s := СМ" % mean
            return "М%s+%s := СМ" % (m.group(1), o.split("(")[0].strip("'"))
        return "%s := СМ" % o.split("(")[0][:24]
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
        # УИА задаёт индексный регистр АДРЕСОМ, а не содержимым памяти
        m = re.search(r"\(М(\d+)\)", o)
        val = o.split("(")[0].strip() or "0"
        if not m:
            return "ИР := адрес %s" % val[:16]
        if val == "0":
            return "М%s := база модуля" % m.group(1)
        return "М%s := адрес %s" % (m.group(1), val[:16])
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
        return ("СМ += %s" % ((mean or o)[:40]) + tail) if o \
            else "СМ += (адрес)" + tail
    if i == "ВЧ":
        return "СМ -= %s" % ((mean or o)[:40]) if o else "СМ -= (адрес)"
    if i == "ВЧОБ":
        return "СМ := (адрес) - СМ"
    if i == "ВЧАБ":
        return "СМ -= |адрес|"
    if i == "ЗНАК":
        return "СМ := -СМ (инверсия знака)"
    if i == "И":
        return "СМ &= %s" % ((mean or o)[:40]) if o else "СМ &= (адрес)"
    if i == "ИЛИ":
        return "СМ |= %s" % ((mean or o)[:40]) if o else "СМ |= (адрес)"
    if i == "НТЖ":
        return "СМ ^= %s" % ((mean or o)[:40]) if o else "СМ ^= (адрес)"
    if i == "ДЕЛ":
        return "СМ /= %s" % ((mean or o)[:40]) if o else "деление"
    if i == "УМН":
        return "СМ *= %s" % ((mean or o)[:40]) if o else "умножение"
    if i == "СБР":
        return "сборка битов: %s" % ((mean or o)[:40]) if o else "сборка битов"
    if i == "РЗБ":
        return "разборка битов: %s" % ((mean or o)[:40]) if o else "разборка битов"
    if i == "ЧЕД":
        return "СМ := кол-во единиц в %s" % ((mean or o)[:40]) if o \
            else "число единиц"
    if i == "НЕД":
        return "СМ := № старш. единицы: %s" % o[:12] if o else "№ старш. единицы"
    if i == "СЛП":
        return "порядок += %s" % o[:15] if o else "сложение порядков"
    if i == "ВЧП":
        return "порядок -= %s" % o[:15] if o else "вычитание порядков"
    if i == "СД":
        m = re.search(r"М(\d+)", o)
        return "сдвиг СМ на М%s" % m.group(1) if m else "сдвиг СМ"
    if i == "РЖ":
        return "РЖ := СМ (режим ждущ.акк.)"
    if i == "РЖА":
        if not o:
            return "РЖ по адресу"
        m = re.match(r"^'([0-7]+)'$", o)
        if m:
            v = int(m.group(1), 8)
            mode = RZH_MODES.get(v)
            return "РЖ := %d (%s)" % (v, mode) if mode else "РЖ := %d" % v
        return "РЖ := %s" % o[:15]
    if i == "СЧРЖ":
        return "СМ := РЖ (режим ждущ.акк.)"
    if i == "СЧМР":
        return "СМ := РМР (результат мантиссы)"
    if i == "СЛПА":
        return "порядок += %s" % o[:10] if o else "порядок += N"
    if i == "ВЧПА":
        return "порядок -= %s" % o[:10] if o else "порядок -= N"
    if i == "МОДА":
        # МОДА: регистр модифицированного адреса (М16) := адрес операнда;
        # адрес следующей команды увеличивается на М16
        if not o or o == "0":
            return "мод.адрес := 0 (сброс модификации)"
        return "мод.адрес := %s" % o[:20]
    if i == "МОД":
        # МОД: М16 := код слова по адресу операнда; адрес следующей
        # команды увеличивается на этот код
        return "мод.адрес := код из %s" % o[:16] if o else "мод.адрес := код"
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
        # УИМ: регистр := СМ, затем СМ := вершина магазина
        m = re.search(r"М(\d+)", o)
        return "М%s := СМ; СМ := из магазина" % m.group(1) if m \
            else "ИР := СМ; СМ := из магазина"
    if i == "СЧИМ":
        # СЧИМ: запись СМ в магазин, затем СМ := регистр
        m = re.search(r"М(\d+)", o)
        return "в магазин; СМ := М%s" % m.group(1) if m \
            else "в магазин; СМ := ИР"
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

    Словарь labels ключуется номером команды (в слове две команды), а
    смещения DMS заданы в словах, поэтому номер команды = 2 * смещение.
    """
    items = []
    for off, half in insns:
        dec = decode(half)
        instr = (dec["name"] or "").upper()
        op = operand_text(dec, ext, labels, module)
        items.append((off, instr, op, local_offset(half)))
    used = set(ext.values())   # имена внешних символов заняты
    result = {}
    # ссылки на константы и переменные (вне раздела команд) - по номеру
    # слова в соответствующем разделе; именуются первыми, чтобы имена
    # вида К<n> и V<n> не достались меткам команд
    for off in sorted(labels):
        if off < 2 * cmdwords:
            continue
        if off < 2 * (cmdwords + constwords):
            base = "К%d" % (off // 2 - cmdwords)
        else:
            base = "V%d" % (off // 2 - cmdwords - constwords)
        name = unique_name(base, used, fallback="L%04o" % off)
        used.add(name)
        result[off] = name
    lastn = None            # последняя загрузка смещения в М7
    # обратные переходы - цели циклов
    loops = set()
    for i, (off, instr, op, ref) in enumerate(items):
        if instr in ("ПБ", "ПО", "ПЕ") and ref is not None:
            if 2 * ref < off:
                loops.add(2 * ref)
    for i, (off, instr, op, ref) in enumerate(items):
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
            _, ins, o, _r = items[k]
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
                    base = subject("F%s" % cand if cand else "")
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
    return result


MODINFO = {}


def dms_labels(lib, name, code):
    """Локальные метки модуля: номер команды -> имя.

    Смещения в формате DMS - СЛОВА от начала модуля (записаны
    восьмерично), а в слове две команды, поэтому номер команды
    = 2 * смещение.  Смещения >= числа слов раздела команд относятся
    к разделу констант и к bss.
    """
    ext, dms, symtab = symbol_table(lib, name)
    labels = {2 * off: nm for off, nm in dms.items()}
    # локальные метки, на которые ссылаются команды, но которые не названы
    # в таблице символов, получают автоматические имена
    for off in local_refs(code):
        labels.setdefault(2 * off, "L%04o" % off)
    return ext, labels, symtab


def info(lib, name):
    """Сведения о модуле: имена меток, символы, выходы (с кэшем)."""
    if name in MODINFO:
        return MODINFO[name]
    s, h = lib.objects[name]
    code = lib.words[s + 3:s + 3 + h["cmd"]]
    ext, labels, symtab = dms_labels(lib, name, code)
    labels[0] = sanitize(name) or name
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
    ext, labels, symtab = dms_labels(lib, name, code)
    # начало модуля - его точка входа
    labels[0] = sanitize(name) or name
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
    frame = set()
    mod = None            # операнд МОДА/МОД: адрес след. команды += М16
    for off, half in insns:
        dec = decode(half)
        instr = (dec["name"] or "???").upper()
        op = operand_text(dec, ext, labels, entry)
        for m in re.finditer(r"(?<![A-Za-zА-Яа-яЁё])М(\d+)", op):
            regs.add(int(m.group(1), 8))
        for m in re.finditer(r"(\d+)\(М7\)", op):
            frame.add(int(m.group(1)))
        for m in re.finditer(r"'([0-7]+)'\(М7\)", op):
            frame.add(int(m.group(1), 8))
        lbl = ""
        if off in labels and off != 0:
            lbl = labels[off]
        code_part = "%-9s%-7s%s" % (lbl, instr, op)
        comment = gen_comment(instr, op, ext, mod)
        if comment:
            comment = comment[:MAX_COMMENT]
        note = LABEL_NOTES.get(name, {}).get(off) if off else None
        if note:
            lines.append("* " + note)
        lines.append(with_comment(code_part.rstrip(), comment))
        # модификатор адреса действует на следующую команду
        if instr in ("МОДА", "МОД"):
            mod = (instr, op) if op and op != "0" else None
        else:
            mod = None
        if instr == "ПБ":
            # конец базового блока - отделяем звёздочкой
            lines.append("*")
    return lines, bases, offsets, sorted(regs), h, ext, labels, exits, sorted(frame)


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
    lines, bases, offsets, regs, h, ext, labels, exits, frame = module_text(
        lib, name, loadmap)
    sites = CALL_SITES
    s = lib.objects[name][0]
    sec = lib.sections(name)
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
    absyms = abs_symbols(lib, name)
    if absyms:
        items = ["%s = %d" % (nm, val - 0o100000 if val >= 0o77700 else val)
                 for nm, val in sorted(absyms.items())]
        head.extend(wrap_head("*   Абсолютные символы: ", items))
    if frame:
        # слоты кадра: общие (0..10) и собственная область модуля;
        # значения >= OUTSIDE - адреса вне кадра (системные области)
        common = [x for x in frame if x <= FRAME_COMMON]
        own = [x for x in frame if FRAME_COMMON < x < OUTSIDE]
        out = [x for x in frame if x >= OUTSIDE]
        items = []
        if common:
            items.append("общие %s" % ranges(common))
        if own:
            items.append("свои %s" % ranges(own))
        if out:
            items.append("вне кадра %s" % ranges(out))
        head.extend(wrap_head("*   Смещения в кадре (М7): ", items))
    if regs:
        head.extend(wrap_head("*   Регистры: ",
                              ["М%o (%s)" % (r, REG_ROLES.get(r, "рабочий регистр"))
                               for r in regs]))
    if any("мод.адрес :=" in ln for ln in lines):
        head.append("*   Модификатор адреса: МОДА/МОД задают М16, "
                    "адрес следующей команды += М16")
    head.append("*" * 51)
    out = list(head)
    # таблица символов модуля - по ней сборщик находит внешние имена
    out.append("*** %s" % SYM_MARK)
    for num, nm in sorted(ext.items()):
        out.append("*   %03d %s" % (num, nm))
    out.append("*")
    # локальные символы вне раздела команд (ссылки на константы и
    # переменные) - сборщику нужны их смещения; смещение в словах
    # от начала модуля (как его записывает загрузчик DMS).
    # Для констант указывается и значение - чтобы текст был полным
    # исходником, который можно собрать настоящим транслятором.
    offs = [off for off in sorted(labels) if off >= 2 * h["cmd"]]
    if offs:
        out.append("* %s (имя - смещение в словах от начала модуля;"
                   " для констант - значение):" % LOCAL_MARK)
        for off in offs:
            w = off // 2
            if w < h["cmd"] + h["const"]:
                val = lib.words[sec["const"] + w - h["cmd"]]
                out.append("*   %-6s %o    %012o" % (labels[off], w, val))
            else:
                out.append("*   %-6s %o" % (labels[off], w))
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
