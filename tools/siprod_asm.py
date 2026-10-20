#!/usr/bin/env python3
"""Обратная сборка кода БЕМШ: проверка соответствия дизассемблирования
и сборка программы из откомментированных текстов.

Формат 24-битной команды БЕМШ (как в диспаке, defs.h):

    биты 23..20  регистр
    бит  19      признак 1-й структуры (мода, по, пб, ...)
    бит  18      признак расширения адреса
    бит  21      признак перемещаемого адреса (формат DMS)
    биты 17..12  код операции (2-я структура) / биты 18..15 (1-я структура)
    биты 11..0   адрес (12 бит) или 15 бит для 1-й структуры

В слове 48 бит две команды: старшие 24 бита - левая, младшие - правая.

Инструмент `disbesm6` печатает код по таблице, приведённой ниже; здесь
та же таблица используется для обратной сборки: команда разбирается на
поля и собирается обратно, после чего результат сравнивается с исходным
словом.  Расхождений быть не должно - это и есть проверка того, что
разбор формата выполнен верно.

Кроме того, по текстам модулей (`text/<модуль>.be`, правила оформления -
как в re-dispak) собирается вся библиотека: ключ `--build` разбирает
тексты, собирает команды и записывает образ, который затем кладётся в
PERSO и проверяется запуском (см. tests/siprod/perso_test.sh).

Использование:
    tools/siprod_asm.py              # проверка всех модулей
    tools/siprod_asm.py SCAN SPAUD   # только указанные модули
    tools/siprod_asm.py --build=lib.bin   # собрать библиотеку из текстов
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from siprod_lib import Library  # noqa: E402

# код операции, маска, тип операнда (как в disbesm6.c)
OPS = [
    ("зп", 0x000000, 0x0bf000, "str1"), ("зпм", 0x001000, 0x0bf000, "str1"),
    ("рег", 0x002000, 0x0bf000, "imm"), ("счм", 0x003000, 0x0bf000, "str1"),
    ("сл", 0x004000, 0x0bf000, "str1"), ("вч", 0x005000, 0x0bf000, "str1"),
    ("вчоб", 0x006000, 0x0bf000, "str1"), ("вчаб", 0x007000, 0x0bf000, "str1"),
    ("сч", 0x008000, 0x0bf000, "str1"), ("и", 0x009000, 0x0bf000, "str1"),
    ("нтж", 0x00a000, 0x0bf000, "str1"), ("слц", 0x00b000, 0x0bf000, "str1"),
    ("знак", 0x00c000, 0x0bf000, "str1"), ("или", 0x00d000, 0x0bf000, "str1"),
    ("дел", 0x00e000, 0x0bf000, "str1"), ("умн", 0x00f000, 0x0bf000, "str1"),
    ("сбр", 0x010000, 0x0bf000, "str1"), ("рзб", 0x011000, 0x0bf000, "str1"),
    ("чед", 0x012000, 0x0bf000, "str1"), ("нед", 0x013000, 0x0bf000, "str1"),
    ("слп", 0x014000, 0x0bf000, "str1"), ("вчп", 0x015000, 0x0bf000, "str1"),
    ("сд", 0x016000, 0x0bf000, "str1"), ("рж", 0x017000, 0x0bf000, "str1"),
    ("счрж", 0x018000, 0x0bf000, "imm"), ("счмр", 0x019000, 0x0bf000, "imm64"),
    ("увв", 0x01b000, 0x0bf000, "imm"), ("слпа", 0x01c000, 0x0bf000, "imm64"),
    ("вчпа", 0x01d000, 0x0bf000, "imm64"), ("сда", 0x01e000, 0x0bf000, "imm64"),
    ("ржа", 0x01f000, 0x0bf000, "imm"), ("уи", 0x020000, 0x0bf000, "reg1"),
    ("уим", 0x021000, 0x0bf000, "reg1"), ("счи", 0x022000, 0x0bf000, "reg1"),
    ("счим", 0x023000, 0x0bf000, "reg1"), ("уии", 0x024000, 0x0bf000, "reg1"),
    ("сли", 0x025000, 0x0bf000, "reg1"), ("Э50", 0x028000, 0x0bf000, "immex"),
    ("Э51", 0x029000, 0x0bf000, "immex"), ("Э52", 0x02a000, 0x0bf000, "immex"),
    ("Э53", 0x02b000, 0x0bf000, "immex"), ("Э54", 0x02c000, 0x0bf000, "immex"),
    ("Э55", 0x02d000, 0x0bf000, "immex"), ("Э56", 0x02e000, 0x0bf000, "immex"),
    ("Э57", 0x02f000, 0x0bf000, "immex"), ("Э60", 0x030000, 0x0bf000, "addrex"),
    ("Э61", 0x031000, 0x0bf000, "addrex"), ("Э62", 0x032000, 0x0bf000, "immex"),
    ("Э63", 0x033000, 0x0bf000, "immex"), ("Э64", 0x034000, 0x0bf000, "addrex"),
    ("Э65", 0x035000, 0x0bf000, "immex"), ("Э66", 0x036000, 0x0bf000, "immex"),
    ("Э67", 0x037000, 0x0bf000, "addrex"), ("Э70", 0x038000, 0x0bf000, "addrex"),
    ("Э71", 0x039000, 0x0bf000, "addrex"), ("Э72", 0x03a000, 0x0bf000, "addrex"),
    ("Э73", 0x03b000, 0x0bf000, "addrex"), ("Э74", 0x03c000, 0x0bf000, "stop"),
    ("Э75", 0x03d000, 0x0bf000, "addrex"), ("Э76", 0x03e000, 0x0bf000, "immex"),
    ("Э77", 0x03f000, 0x0bf000, "immex"),
    ("мода", 0x090000, 0x0f8000, "addrmod"), ("мод", 0x098000, 0x0f8000, "addrmod"),
    ("уиа", 0x0a0000, 0x0f8000, "reg2"), ("слиа", 0x0a8000, 0x0f8000, "reg2"),
    ("по", 0x0b0000, 0x0f8000, "branch"), ("пе", 0x0b8000, 0x0f8000, "branch"),
    ("пб", 0x0c0000, 0x0f8000, "jump"), ("пв", 0x0c8000, 0x0f8000, "call"),
    ("выпр", 0x0d0000, 0x0f8000, "iret"), ("стоп", 0x0d8000, 0x0f8000, "imm2"),
    ("пио", 0x0e0000, 0x0f8000, "branch"), ("пино", 0x0e8000, 0x0f8000, "branch"),
    ("пио36", 0x0f0000, 0x0f8000, "branch"), ("цикл", 0x0f8000, 0x0f8000, "branch"),
]

DMS_BIT = 0x200000       # признак перемещаемого адреса (бит 21)
STRUCT_BIT = 0x80000     # признак 1-й структуры (бит 19)
EXP_BIT = 0x40000        # признак расширения адреса (бит 18)

# обратная таблица: мнемоника -> (код, маска, тип операнда)
OPCODE_BY_NAME = {}
for _n, _c, _m, _k in OPS:
    OPCODE_BY_NAME[_n.upper()] = (_c, _m, _k)


def lookup(half):
    """Код операции по таблице (как в disbesm6)."""
    for name, code, mask, kind in OPS:
        if half & mask == code:
            return name, code, mask, kind
    return None, 0, 0, "illegal"


def decode(half):
    """Разбор 24-битной команды в поля."""
    name, code, mask, kind = lookup(half)
    reg = (half >> 20) & 0xF
    dms = 1 if half & DMS_BIT else 0
    struct = 1 if half & STRUCT_BIT else 0
    if struct:
        # 1-я структура: код операции - биты 18..15, адрес - 15 бит
        op = (half >> 15) & 0xF
        addr = half & 0o77777
        exp = 0
    else:
        # 2-я структура: код операции - биты 17..12, адрес - 12 бит
        op = (half >> 12) & 0o77
        exp = 1 if half & EXP_BIT else 0
        addr = (half & 0o7777) + (0o700000 if exp else 0)
    return dict(name=name, kind=kind, reg=reg, arg=addr, dms=dms, exp=exp,
                op=op, struct=struct, raw=half)


def encode(dec):
    """Сборка 24-битной команды из полей."""
    if dec["kind"] == "illegal":
        return dec["raw"]
    half = (dec["reg"] << 20) | (dec["op"] << (15 if dec["struct"] else 12))
    if dec["struct"]:
        half |= dec["arg"] & 0o77777
    else:
        half |= dec["arg"] & 0o7777
        if dec["arg"] & 0o700000:
            half |= EXP_BIT
    if dec["dms"]:
        half |= DMS_BIT
    if dec["struct"]:
        half |= STRUCT_BIT
    return half


def check_module(lib, name):
    """Проверка обратной сборки раздела команд модуля."""
    s, h = lib.objects[name]
    bad = []
    for i in range(h["cmd"]):
        word = lib.words[s + 3 + i]
        for half in (word >> 24, word & 0xffffff):
            dec = decode(half)
            if encode(dec) != half:
                bad.append((i, half, dec, "разбор/сборка"))
                continue
            # код операции в таблице должен совпадать с разобранным
            opname, code, mask, kind = lookup(half)
            if opname is None:
                bad.append((i, half, dec, "нет кода операции"))
                continue
            shift = 15 if dec["struct"] else 12
            if (code >> shift) & (0xF if dec["struct"] else 0o77) != dec["op"]:
                bad.append((i, half, dec, "код операции " + opname))
    return bad


def assemble_module(lib, name):
    """Пересборка раздела команд модуля из разобранных команд."""
    s, h = lib.objects[name]
    words = []
    for i in range(h["cmd"]):
        word = lib.words[s + 3 + i]
        halves = []
        for half in (word >> 24, word & 0xffffff):
            halves.append(encode(decode(half)))
        words.append((halves[0] << 24) | halves[1])
    return words


# ═══════════════════════════════════════════════════════════════════
# СБОРКА ИЗ ТЕКСТОВ (text/<модуль>.be)
# ═══════════════════════════════════════════════════════════════════

SYM_MARK = "СИМВОЛЫ МОДУЛЯ"
LOCAL_MARK = "ЛОКАЛЬНЫЕ СИМВОЛЫ"


def strip_comment(line):
    """Убрать комментарий (запятая с отступом) из строки текста."""
    m = re.search(r"\s{2,},", line)
    if m:
        return line[:m.start()].rstrip()
    return line.rstrip()


def parse_text(path):
    """Разбор текста БЕМШ: символы, метки, команды.

    Возвращает (syms, labels, instrs):
      syms   - словарь номер символа -> имя;
      labels - словарь имя метки -> смещение (в словах от начала
               модуля, как его записывает загрузчик DMS);
      instrs - список (смещение, мнемоника, операнд); смещение - номер
               команды (в слове две команды).

    Метки раздела команд стоят перед командой, номер которой вдвое
    больше смещения DMS, поэтому смещение метки = номер команды // 2.
    Смещения из раздела локальных символов уже заданы в словах и
    берутся как есть.
    """
    syms = {}
    labels = {}
    instrs = []
    in_syms = False
    in_locals = False
    for raw in open(path):
        line = raw.rstrip("\n")
        if line.startswith("*"):
            if SYM_MARK in line:
                in_syms = True
                in_locals = False
                continue
            if LOCAL_MARK in line:
                in_locals = True
                in_syms = False
                continue
            if in_syms:
                m = re.match(r"^\*\s+(\d+)\s+(.*?)\s*$", line)
                if m:
                    syms[int(m.group(1))] = m.group(2)
                    continue
                in_syms = False
            if in_locals:
                m = re.match(r"^\*\s+(\S+)\s+(\d+)(?:\s+([0-7]+))?\s*$", line)
                if m:
                    labels[m.group(1)] = int(m.group(2), 8)
                    continue
                in_locals = False
            continue
        code = strip_comment(line)
        if not code.strip():
            continue
        parts = code.split(None, 1)
        first = parts[0]
        rest = parts[1].strip() if len(parts) > 1 else ""
        if len(parts) > 1 and parts[1].split(None, 1)[0].upper() in ("КОНД", "ПАМ"):
            continue                # объявление константы или переменной
        if first.upper() == "ФИНИШ":
            continue
        if first.upper() == "СТАРТ":
            # метка перед СТАРТ - вход в модулю
            labels[first] = len(instrs) // 2
            continue
        if first.upper() in OPCODE_BY_NAME:
            instrs.append((len(instrs), first.upper(), rest))
            continue
        # первое слово - метка
        if len(instrs) % 2:
            # метка обязана стоять в начале слова: смещение DMS - слово
            raise ValueError("метка %s: номер команды %d нечётный"
                             % (first, len(instrs)))
        labels[first] = len(instrs) // 2
        parts = rest.split(None, 1)
        if not parts:
            continue
        if parts[0].upper() == "СТАРТ":
            # объявление начала модуля - команды не содержит
            continue
        instrs.append((len(instrs), parts[0].upper(),
                       parts[1].strip() if len(parts) > 1 else ""))
    return syms, labels, instrs


def resolve_operand(body, syms, labels, symindex):
    """Операнд -> (значение адресного поля, признак перемещаемости)."""
    if not body:
        return 0, 0
    if body in labels:
        return 0o40000 + labels[body], 0
    if body in symindex:
        return 0o74000 + symindex[body], 0
    if body.startswith("'"):
        return int(body.strip("'"), 8), 0
    if body.startswith("-"):
        return int(body) + 0o100000, 0
    if body.isdigit():
        return int(body), 0
    raise ValueError("не разобран операнд: %r" % body)


def assemble_text(path):
    """Сборка команд модуля по его тексту БЕМШ."""
    syms, labels, instrs = parse_text(path)
    symindex = {}
    for num, name in syms.items():
        symindex.setdefault(name, num)
    words = []
    cur = {}
    for off, instr, op in instrs:
        if instr not in OPCODE_BY_NAME:
            raise ValueError("неизвестная команда: %s" % instr)
        code, mask, kind = OPCODE_BY_NAME[instr]
        # отделить индексный регистр
        m = re.match(r"^(.*?)\(М(\d+)\)$", op)
        if m:
            body, reg = m.group(1).strip(), int(m.group(2), 8)
        else:
            body, reg = op, 0
        if kind == "reg1":
            mm = re.match(r"^М(\d+)$", body)
            low = int(mm.group(1), 8) if mm else 0
            half = (code & ~DMS_BIT) | (reg << 20) | (low & 0o37)
        elif kind in ("imm", "immex"):
            val = int(body.strip("'"), 8) if body.strip("'") else 0
            half = (code & ~DMS_BIT) | (reg << 20) | (val & 0o7777)
        elif kind == "imm64":
            v = 64
            mm = re.match(r"^64([-+]\d+)?$", body)
            if mm and mm.group(1):
                v = 64 + int(mm.group(1))
            half = (code & ~DMS_BIT) | (reg << 20) | (v & 0o177)
        elif kind == "imm2":
            half = (code & ~DMS_BIT) | (reg << 20) | (int(body) & 0o77777)
        else:
            val, _ = resolve_operand(body, syms, labels, symindex)
            if code & STRUCT_BIT:
                # 1-я структура: адрес 15 бит
                half = (code & ~DMS_BIT) | (reg << 20) | (val & 0o77777)
            else:
                half = (code & ~DMS_BIT) | (reg << 20) | (val & 0o7777)
                if val & 0o700000:
                    half |= EXP_BIT
        words.append(half)
    # слова: по две команды
    out = []
    for i in range(0, len(words), 2):
        hi = words[i]
        lo = words[i + 1] if i + 1 < len(words) else 0
        out.append((hi << 24) | lo)
    return out, labels, syms


def build_library(lib, textdir, out):
    """Сборка библиотеки из текстов модулей.

    Код каждого модуля собирается по тексту; остальные разделы объекта
    (каталог, таблица символов, константы) берутся из исходного образа -
    так же, как загрузчик берёт объект из библиотеки.
    """
    data = bytearray(lib.data)
    report = []
    for name, (s, h) in sorted(lib.objects.items()):
        path = os.path.join(textdir, name.replace("*", "#") + ".be")
        if not os.path.exists(path):
            report.append((name, "нет текста"))
            continue
        words, labels, syms = assemble_text(path)
        if len(words) != h["cmd"]:
            report.append((name, "команд %d вместо %d" % (len(words), h["cmd"])))
            continue
        same = True
        for i, w in enumerate(words):
            if w != lib.words[s + 3 + i]:
                same = False
                break
        for i, w in enumerate(words):
            off = (s + 3 + i) * 6
            data[off:off + 6] = w.to_bytes(6, "big")
        report.append((name, "собрано, совпадает" if same else
                       "собрано, РАЗЛИЧАЕТСЯ"))
    with open(out, "wb") as f:
        f.write(data)
    return report


def emit_library(lib, path):
    """Запись библиотеки, в которой разделы команд пересобраны заново."""
    data = bytearray(lib.data)
    for name, (s, h) in lib.objects.items():
        words = assemble_module(lib, name)
        for i, w in enumerate(words):
            off = (s + 3 + i) * 6
            data[off:off + 6] = w.to_bytes(6, "big")
    with open(path, "wb") as f:
        f.write(data)
    return path


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    opts = [a for a in sys.argv[1:] if a.startswith("-")]
    path = "siprod.bin"
    if args and os.path.exists(args[0]):
        path = args.pop(0)
    lib = Library(path)
    for o in opts:
        if o.startswith("--emit="):
            out = emit_library(lib, o[7:])
            print("пересобранная библиотека: %s" % out)
            return 0
        if o.startswith("--build="):
            textdir = "text"
            for oo in opts:
                if oo.startswith("--text="):
                    textdir = oo[7:]
            out = o[8:]
            report = build_library(lib, textdir, out)
            bad = 0
            for name, msg in report:
                if "РАЗЛИЧАЕТСЯ" in msg or "нет текста" in msg or "вместо" in msg:
                    print("%-10s %s" % (name, msg))
                    bad += 1
            print("собрано модулей: %d, расхождений: %d -> %s"
                  % (len(report) - bad, bad, out))
            return 1 if bad else 0
    names = args if args else sorted(lib.objects)
    total = 0
    for name in names:
        bad = check_module(lib, name)
        total += len(bad)
        status = "OK" if not bad else "ОШИБКА %d" % len(bad)
        print("%-10s %s" % (name, status))
        for i, half, dec, why in bad[:3]:
            print("    слово %d: %06x: %s" % (i, half, why))
    print("всего расхождений: %d" % total)
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
