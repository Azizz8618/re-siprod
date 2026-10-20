#!/usr/bin/env python3
"""Сборка модулей СИПРОДа настоящим транслятором МАКРО-БЕМШ.

Тексты `text/<модуль>.be` - это результат дизассемблирования, а не исходники:
их нельзя подать транслятору как есть.  Здесь они переводятся в исходный
синтаксис МАКРО-БЕМШ (как в проекте re-dispak) и компилируются штатным
транслятором ИПМ МАКРО-БЕМШ ВЕР.06/78, который работает в эмуляторе диспака.

Проверяется:
  * транслятор не выдаёт ошибок;
  * мнемоники и регистры скомпилированных команд совпадают с оригиналом;
  * ссылки на локальные метки ведут туда же, куда ведут в оригинале
    (т.е. метки в текстах стоят на нужных командах);
  * ссылки на внешние символы указывают на те же элементы, что и в оригинале.

Сборка библиотеки: раздел команд каждого модуля берётся из скомпилированного
кода, остальные разделы объекта (таблица символов, константы, каталог) - из
исходного образа: транслятор 1978 г. пишет объект в формате ДИСПАК (с
запакованным заголовком и своими кодами перемещений), а библиотеку СИПРОДа
читает Монитор-80 (формат DMS).  Поэтому код пересобирается в формат DMS:
адреса локальных меток - в смещения от начала модуля, ссылки на внешние
символы - в номера записей таблицы символов.

Запуск:
    tools/siprod_bemsh.py [МОДУЛЬ...]      # по умолчанию - все модули
    tools/siprod_bemsh.py -v МОДУЛЬ        # показать исходник и листинг
    tools/siprod_bemsh.py --build=FILE     # собрать библиотеку
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from siprod_lib import Library                      # noqa: E402
from siprod_dis import symbol_table, sanitize     # noqa: E402
from siprod_asm import decode, OPS as ASM_OPS     # noqa: E402

# адрес загрузки модуля в скомпилированном образе (источник без адреса)
LOAD = 1

# номер версии библиотеки (счётчик в датах записей каталога DMS).
# У исходной библиотеки СИПРОДа счётчик = 52.
VERSION = 53

# том, в котором лежит транслятор и личная библиотека
VOL = "2248"
TAPE = "43"                 # лента зон PERSO
WORK = os.environ.get("SIPROD_BEMSH_WORK", "/tmp/siprod-bemsh")
ZONE = os.environ.get("SIPROD_BEMSH_ZONE", "3900")

# команды МАКРО-БЕМШ, которые встречаются в модулях СИПРОДа:
# полный список кодов операций (таблица disbesm6)
OPS = set(name.upper() for name, _c, _m, _k in ASM_OPS)

# разбор адресного поля команды 1-й структуры: 15 бит, биты 14..12 - признак
LOC_TAG = 0o4
SYM_TAG = 0o7

# признак перемещаемого адреса в формате DMS
DMS_BIT = 0x200000
# признак 1-й структуры
STRUCT_BIT = 0x80000


def parse_be(path):
    """Текст .be -> (локальные символы, метки, команды).

    Метки: имя -> (номер команды, смещение DMS в словах от начала модуля).
    Локальные символы: имя -> смещение DMS в словах (константы и bss).
    """
    locsyms, labels, instrs = {}, {}, []
    mode = None
    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        if line.startswith("***"):
            mode = line.strip()
            continue
        if line.startswith("*"):
            if "ЛОКАЛЬНЫЕ" in line:
                mode = "ЛОКАЛЬНЫЕ"
                continue
            if mode and "ЛОКАЛЬНЫЕ" in mode:
                m = re.match(r"^\*\s+(\S+)\s+(\d+)\s*$", line)
                if m:
                    locsyms[m.group(1)] = int(m.group(2), 8)
            continue
        code = re.sub(r"\s{2,},.*$", "", line).rstrip()
        if not code.strip():
            continue
        parts = code.split(None, 1)
        first = parts[0]
        rest = parts[1].strip() if len(parts) > 1 else ""
        if first.upper() == "СТАРТ":
            labels[first] = (len(instrs), len(instrs) // 2)
            continue
        if re.match(r"^[А-ЯЁA-Z][А-ЯЁA-Z0-9]*$", first) and first.upper() not in OPS:
            labels[first] = (len(instrs), len(instrs) // 2)
            if not rest:
                continue
            p2 = rest.split(None, 1)
            if p2[0].upper() == "СТАРТ":
                # имя модуля перед СТАРТ - вход в модуль
                continue
            instrs.append((len(instrs), p2[0].upper(),
                           p2[1].strip() if len(p2) > 1 else "", first))
            continue
        instrs.append((len(instrs), first.upper(), rest, None))
    return locsyms, labels, instrs


def signed15(off):
    """Смещение 15 бит со знаком: значения от 0o40000 - отрицательные."""
    return off - 0o100000 if off >= 0o40000 else off


def ext_names(lib, name):
    """Внешние символы модуля: имя в тексте -> (имя блока, смещение).

    Имя общего блока в таблице символов DMS помечено звёздочками
    ("*LYG*"), в исходнике МАКРО-БЕМШ их не пишут.  Элемент общего блока
    задаётся как ИМЯ+СМЕЩЕНИЕ, поэтому смещение отделяется от имени.
    Смещения в ссылках - 15 бит со знаком (0o77777 = -1).
    """
    ext, _labels, symtab = symbol_table(lib, name)

    def resolve(i, depth=0):
        """Имя символа (с учётом цепочки ссылок) и суммарное смещение."""
        if i >= len(symtab) or depth > 8:
            return None, 0
        if i == 0:
            return name, 0        # запись 0 - имя самого модуля
        e = symtab[i]
        if e is None:
            return None, 0
        if e[0] in ("subp", "lc", "lp"):
            return e[1].strip("*"), 0
        if e[0] == "ref":
            base, off = resolve(e[1], depth + 1)
            if base:
                return base, off + signed15(e[2])
        return None, 0

    out = {}
    for i, e in enumerate(symtab):
        if not e:
            continue
        nm = ext.get(i)
        if nm is None:
            continue
        if e[0] in ("subp", "lc", "lp") and e[1]:
            out[nm] = (sanitize(e[1]), 0)
        elif e[0] == "ref":
            base, off = resolve(i)
            if base:
                out[nm] = (sanitize(base), off)
    return out


def bemsh_name(name, dms):
    """Имя метки в синтаксисе МАКРО-БЕМШ: буква и цифры.

    Имена вида L12A транслятор не принимает, поэтому локальные метки
    переименовываются в L<смещение>: по имени восстанавливается смещение
    метки в скомпилированном модуле.
    """
    return "L%o" % dms


def operand_text(op, ext, consts, bss, labels):
    """Операнд команды в синтаксисе МАКРО-БЕМШ.

    В МАКРО-БЕМШ нулевое смещение не пишется, элемент общего блока
    указывается как ИМЯ+СМЕЩЕНИЕ, а символ с абсолютным адресом
    (отрицательное смещение) - как обычное число.
    """
    op = op.strip()
    m = re.match(r"^(.*?)\(М(\d+)\)$", op)
    body, reg = (m.group(1), m.group(2)) if m else (op, None)
    if body in labels:
        name = bemsh_name(body, labels[body][1])
    elif body in consts or body in bss:
        name = body
    elif body in ext:
        base, off = ext[body]
        if not off:
            name = base
        elif off > 0:
            name = "%s+%d" % (base, off)
        else:
            name = "%s%d" % (base, off)
    elif body in abs_syms:
        name = "%d" % abs_syms[body]
    elif body == "0":
        name = ""
    else:
        name = body
    if reg:
        return "%s(М%s)" % (name, reg) if name else "(М%s)" % reg
    return name


def bss_name(n):
    """Имя n-го слова раздела bss."""
    return "V%d" % n


# символы с абсолютным адресом (обычно отрицательные смещения)
abs_syms = {}


def convert(lib, name, path):
    """Текст .be -> исходник МАКРО-БЕМШ."""
    global abs_syms
    s, h = lib.objects[name]
    sec = lib.sections(name)
    locsyms, labels, instrs = parse_be(path)
    ext = ext_names(lib, name)
    # символы с абсолютным адресом - в исходнике обычные числа
    abs_syms = {}
    _ext, _labels, symtab = symbol_table(lib, name)
    for i, e in enumerate(symtab):
        if e and e[0] == "abs":
            val = e[1]
            abs_syms[_ext.get(i, "A%d" % val)] = \
                val - 0o100000 if val >= 0o77700 else val
    consts, bss = {}, {}
    for nm, off in locsyms.items():
        if off < h["cmd"]:
            continue
        if off < h["cmd"] + h["const"]:
            consts[nm] = off - h["cmd"]
        else:
            bss[nm] = off - h["cmd"] - h["const"]
    out = ["%s\tСТАРТ" % name, "\tЕ", "\tМ"]
    for off, instr, op, lab in instrs:
        label = ""
        for nm, (cmd, dms) in labels.items():
            if cmd == off and nm not in locsyms:
                label = bemsh_name(nm, dms)
                break
        operand = operand_text(op, ext, consts, bss, labels)
        cmd = "\t%s\t%s" % (instr.lower(), operand) if operand \
            else "\t%s" % instr.lower()
        out.append(("%s\t" % label) + cmd.strip("\t"))
    # объявления данных - в конце модуля: константы и переменные
    for nm in sorted(consts, key=lambda k: consts[k]):
        word = lib.words[sec["const"] + consts[nm]]
        out.append("%s\tконд\tв'%012o'" % (nm, word))
    for n in range(h["bss"]):
        out.append("%s\tпам\t1" % bss_name(n))
    # внешние символы - объявление ВНЕШ (как в re-dispak).  Транслятор
    # 1978 г. обрезает строки длиннее 64 знаков, поэтому список
    # внешних имён разбивается на несколько директив.
    outside = sorted(set(base for base, _off in ext.values()))
    label = "%s\tВНЕШ\t" % name
    line = ""
    for nm in outside:
        piece = nm + ","
        if line and len(label) + len(line) + len(piece) > 64:
            out.append(label + line.rstrip(","))
            line = ""
        line += piece
    if line:
        out.append(label + line.rstrip(","))
    return "\n".join(out) + "\n"


def make_job(src, zone=ZONE, vol=VOL):
    """Исходник -> задание для транслятора МАКРО-БЕМШ."""
    job = ["шифр 419999^", "трак 64^", "лент 30(2048-6200)^", "лент 42(2099)^",
           "лент %s(%s-ЗП)^" % (TAPE, vol), "ацп 40^", "росп 0^", "врем 240^",
           "лист 0-37^", "вход 4000^", "е", "в 4000", "к 00 010 4003",
           "к 15 24 04000", "к 00 066 0001 00 000 0100", "с 3000 67", "в 14000",
           "а1", "ВВД$$$"]
    for line in src.rstrip("\n").split("\n"):
        job.append(line + "^")
    job += ["КВЧ$$$^", "ТРН$$$^", "ЧТКОМП420070^", "1-1^", "БТМАЛФ^",
            "ЗОНМОД%s%s  0001^" % (TAPE, zone), "КНЦ$$$^", "_$ЕКОНЕЦ"]
    return "\n".join(job) + "\n"


def listing_job(src, zone=ZONE, vol=VOL):
    """Задание для листинга (без записи объектного модуля)."""
    job = make_job(src, zone, vol)
    return job.replace("\n1-1^\n", "\n0-0^\n").replace("\nБТМАЛФ^\n", "\n")


def workdir():
    """Рабочий каталог с копией тома."""
    os.makedirs(WORK, exist_ok=True)
    vol = os.path.join(WORK, VOL)
    if not os.path.exists(vol):
        shutil.copy("/usr/local/share/besm6/%s" % VOL, vol)
    return WORK


def run_translator(src, name):
    """Прогнать транслятор; вернуть (листинг, текст ошибок)."""
    work = workdir()
    b6 = os.path.join(work, name + ".b6")
    open(b6, "w", encoding="utf-8").write(listing_job(src))
    env = dict(os.environ, BESM6_PATH=work + ":/usr/local/share/besm6")
    r = subprocess.run(["dispak", b6], capture_output=True, text=True,
                       env=env, cwd=work)
    out = r.stdout + r.stderr
    errs = []
    for line in out.splitlines():
        if "НЕОП" in line or "ЗАПР" in line or "ОШИБКИ" in line:
            errs.append(line.rstrip())
    return out, errs


RIGHT_COL = 49        # начало правой колонки листинга

# код команды в листинге: "рег оп(2) адрес(5)" для 1-й структуры
# и "рег оп(3) адрес(4)" для 2-й; начинается с 31-й колонки
CODE_RE = re.compile(r"(?:^|\s)(\d{2}) (\d{2,3}) +(\d{4,5})\s*$")

# перемещение: "+ <номер символа>+<смещение>" в колонках 12..29
RELOC_RE = re.compile(r"\+\s*(\d+)(?:\+(\d+))?")


def parse_listing(text):
    """Листинг транслятора -> (команды, символы).

    команды - список (пункт исходника, регистр, код операции, адрес,
    перемещение) в порядке пунктов; символы - словарь имя -> адрес
    (из таблицы символов в конце листинга).
    """
    cmds = []
    symbols = {}
    for line in text.splitlines():
        # таблица символов: имя и адрес (в конце листинга)
        for name, addr in re.findall(r"(\S+)\s+(\d{5})", line):
            symbols[name] = int(addr, 8)
        left = line[:RIGHT_COL]
        r = line[RIGHT_COL:].rstrip()
        m = re.match(r"^(\d{4,5})\s+(\d{4,5})\s*(.*)$", r)
        if not m:
            continue
        item = int(m.group(2))
        code = CODE_RE.search(left)
        if code:
            reloc = RELOC_RE.search(left[12:30])
            cmds.append((item, int(code.group(1), 8), int(code.group(2), 8),
                         int(code.group(3), 8),
                         (int(reloc.group(1)),
                          int(reloc.group(2)) if reloc.group(2) else 0)
                         if reloc else None))
    return cmds, symbols


def orig_op(half):
    """Код операции команды в формате DMS (восьмеричное число)."""
    if half & STRUCT_BIT:
        return (half >> 15) & 0o37
    return (half >> 12) & 0o77


def check_module(lib, name, path, verbose=False):
    """Скомпилировать модуль и сравнить с оригиналом."""
    src = convert(lib, name, path)
    text, errs = run_translator(src, name.replace("*", "#"))
    if verbose:
        print(src)
        print(text[-4000:])
    errors = [e for e in errs if "НЕОП" in e or "ЗАПР" in e]
    result = dict(module=name, errors=errors, mismatch=[], code=None)
    if errors:
        return result
    # оригинал: команды и их коды
    s, h = lib.objects[name]
    code = lib.words[s + 3:s + 3 + h["cmd"]]
    locsyms, labels, instrs = parse_be(path)
    _ext, _labels, symtab = symbol_table(lib, name)
    cmds, symbols = parse_listing(text)
    result["code"] = code
    if len(cmds) != len(instrs):
        result["mismatch"].append(
            "команд скомпилировано %d, в тексте %d" % (len(cmds), len(instrs)))
        return result
    for k, (off, instr, op, _lab) in enumerate(instrs):
        item, reg, cop, addr, reloc = cmds[k]
        half = (code[off // 2] >> 24) if off % 2 == 0 else \
            (code[off // 2] & 0xffffff)
        # код операции и регистр должны совпадать
        dop = decode(half)["name"]
        if orig_op(half) != cop:
            result["mismatch"].append(
                "команда %d: код операции %s: %o != %o"
                % (off, dop, orig_op(half), cop))
        oreg = (half >> 20) & 0o17
        if oreg != reg:
            result["mismatch"].append(
                "команда %d: регистр %o != %o" % (off, oreg, reg))
        # адресное поле
        field = half & 0o77777
        if not (half & STRUCT_BIT):
            # 2-я структура: обычный адрес - должен совпасть
            if addr != (half & 0o7777):
                result["mismatch"].append(
                    "команда %d: адрес %o != %o" % (off, addr, half & 0o7777))
            continue
        tag = (field >> 12) & 7
        if tag == LOC_TAG:
            target = field & 0o7777
            if target < h["cmd"]:
                # ссылка на локальную метку: адрес у метки в листинге
                want = symbols.get("L%o" % target)
                if want is None:
                    result["mismatch"].append(
                        "команда %d: нет метки L%o в листинге" % (off, target))
                elif addr != want:
                    result["mismatch"].append(
                        "команда %d: ссылка на %o, метка L%o на %o"
                        % (off, addr, target, want))
            # символ раздела данных - адрес в DMS другой, пропускаем
        elif tag == SYM_TAG:
            # внешний символ: в листинге должно быть перемещение; если
            # символ имеет абсолютный адрес, перемещения нет - адрес
            # записан сразу в команде
            if reloc is None:
                index = field & 0o3777
                e = symtab[index] if index < len(symtab) else None
                if e and e[0] == "abs":
                    want = signed15(e[1]) & 0o77777
                    if addr != want:
                        result["mismatch"].append(
                            "команда %d: абсолютный адрес %o != %o"
                            % (off, addr, want))
                else:
                    result["mismatch"].append(
                        "команда %d: внешний символ без перемещения" % off)
        else:
            # обычный адрес
            if addr != (field & 0o7777):
                result["mismatch"].append(
                    "команда %d: адрес %o != %o" % (off, addr, field & 0o7777))
    return result


def build_module(lib, name, path):
    """Код модуля в формате DMS по скомпилированному коду.

    Транслятор 1978 г. кодирует адреса иначе, чем DMS: локальные метки -
    абсолютными адресами, элементы общих блоков - «блок+смещение», внешние
    символы - перемещениями.  Поэтому берём код операции и регистр из
    скомпилированной команды, а адресное поле - из оригинала (там оно уже
    в формате DMS); равенство адресов проверяется функцией check_module.
    """
    src = convert(lib, name, path)
    text, errs = run_translator(src, name.replace("*", "#"))
    errors = [e for e in errs if "НЕОП" in e or "ЗАПР" in e]
    if errors:
        raise ValueError("%s: ошибки транслятора: %s"
                         % (name, errors[0].strip()))
    s, h = lib.objects[name]
    orig = lib.words[s + 3:s + 3 + h["cmd"]]
    cmds, _symbols = parse_listing(text)
    _locsyms, _labels, instrs = parse_be(path)
    if len(cmds) != len(instrs):
        raise ValueError("%s: скомпилировано %d команд, в тексте %d"
                         % (name, len(cmds), len(instrs)))
    out = []
    for k, (off, instr, op, _lab) in enumerate(instrs):
        _item, reg, cop, _addr, _reloc = cmds[k]
        half = (orig[off // 2] >> 24) if off % 2 == 0 else \
            (orig[off // 2] & 0xffffff)
        struct = 1 if half & STRUCT_BIT else 0
        new = (reg << 20) | (cop << (15 if struct else 12))
        field = half & 0o77777
        if struct:
            new |= field & 0o77777
        else:
            new |= field & 0o7777
            if field & 0o700000:
                new |= 0o40000
        out.append(new)
    words = []
    for i in range(0, len(out), 2):
        hi = out[i]
        lo = out[i + 1] if i + 1 < len(out) else 0
        words.append((hi << 24) | lo)
    return words


def library_version(now=None, version=VERSION):
    """Версия библиотеки - дата в записи каталога DMS.

    В записи каталога биты 47..24 - дата: три поля по 6 бит (минуты,
    секунды, счётчик) и запасное поле.  Счётчик - номер версии
    библиотеки; минуты и секунды - время сборки.
    """
    t = time.localtime(now)
    return ((t.tm_min & 0o77) << 18) | ((t.tm_sec & 0o77) << 12) \
        | ((version & 0o77) << 6)


def version_text(word):
    """Дата из записи каталога -> строка «мин:сек, версия»."""
    date = (word >> 24) & 0xffffff
    minutes = (date >> 18) & 0o77
    seconds = (date >> 12) & 0o77
    version = (date >> 6) & 0o77
    return "%02d:%02d, версия %d" % (minutes, seconds, version)


def library_version_text(lib, path=None):
    """Версия библиотеки.

    Собранная библиотека хранит версию рядом с образом (файл
    <образ>.version): даты в записях каталога проверяет загрузчик
    Монитор-80, менять их нельзя.  У исходной библиотеки версия
    берётся из счётчика в датах каталога.
    """
    if path:
        try:
            with open(path + ".version", encoding="utf-8") as f:
                lines = f.read().splitlines()
            return "%s (%s, %s)" % (lines[0].split(" ", 1)[1],
                                   lines[1].split(" ", 1)[1],
                                   lines[2].split(": ", 1)[1])
        except (IOError, OSError, IndexError):
            pass
    return "%d (исходная библиотека СИПРОДа)" % ((lib.words[3] >> 30) & 0o77)


def build_library(lib, textdir, out, stamp=None, version=VERSION):
    """Сборка библиотеки: код модулей - из транслятора МАКРО-БЕМШ.

    Остальные разделы объектов (таблица символов, константы) и каталог
    берутся из исходного образа: их формат задаёт Монитор-80, а
    транслятор 1978 г. пишет объект в формате ДИСПАК.

    Даты в записях каталога не меняются: загрузчик Монитор-80 проверяет
    их (при изменении библиотека не грузится).  Поэтому версия
    библиотеки записывается рядом с образом - в файл <образ>.version.
    """
    data = bytearray(lib.data)
    report = []
    for name, (s, h) in sorted(lib.objects.items()):
        path = os.path.join(textdir, name.replace("*", "#") + ".be")
        if not os.path.exists(path):
            report.append((name, "нет текста"))
            continue
        try:
            words = build_module(lib, name, path)
        except ValueError as e:
            report.append((name, str(e)))
            continue
        if len(words) != h["cmd"]:
            report.append((name, "команд %d вместо %d"
                           % (len(words), h["cmd"])))
            continue
        same = all(words[i] == lib.words[s + 3 + i] for i in range(len(words)))
        for i, w in enumerate(words):
            off = (s + 3 + i) * 6
            data[off:off + 6] = w.to_bytes(6, "big")
        report.append((name, "собрано, совпадает" if same
                       else "собрано, РАЗЛИЧАЕТСЯ"))
    with open(out, "wb") as f:
        f.write(data)
    # версия библиотеки - в отдельный файл рядом с образом
    t = time.localtime(stamp)
    with open(out + ".version", "w", encoding="utf-8") as f:
        f.write("версия %d\n" % version)
        f.write("собрано %04d-%02d-%02d %02d:%02d\n"
                % (t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min))
        f.write("сборка: МАКРО-БЕМШ ВЕР.06/78\n")
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("modules", nargs="*", help="модули (по умолчанию - все)")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--image", default=os.path.join(ROOT, "siprod.bin"))
    ap.add_argument("--build", default=None,
                    help="собрать библиотеку в этот файл")
    ap.add_argument("--text", default=os.path.join(ROOT, "text"))
    ap.add_argument("--version", action="store_true",
                    help="показать версию библиотеки")
    args = ap.parse_args()
    lib = Library(args.image)
    if args.version:
        print("версия библиотеки: %s" % library_version_text(lib, args.image))
        return 0
    if args.build:
        report = build_library(lib, args.text, args.build)
        bad = 0
        for name, msg in report:
            if "РАЗЛИЧАЕТСЯ" in msg or "нет текста" in msg or "вместо" in msg \
                    or "ошибки" in msg:
                print("%-10s %s" % (name, msg))
                bad += 1
        print("собрано модулей: %d, расхождений: %d -> %s"
              % (len(report) - bad, bad, args.build))
        return 1 if bad else 0
    names = args.modules or sorted(lib.objects)
    bad = 0
    for name in names:
        if name not in lib.objects:
            print("нет модуля: %s" % name, file=sys.stderr)
            continue
        path = os.path.join(ROOT, "text", name.replace("*", "#") + ".be")
        res = check_module(lib, name, path, args.verbose)
        if res["errors"]:
            bad += 1
            print("%-10s ОШИБКИ ТРАНСЛЯТОРА (%d)" % (name, len(res["errors"])))
            for e in res["errors"][:5]:
                print("   ", e.strip())
        elif res["mismatch"]:
            bad += 1
            print("%-10s РАСХОЖДЕНИЯ (%d)" % (name, len(res["mismatch"])))
            for e in res["mismatch"][:5]:
                print("   ", e)
        else:
            print("%-10s OK" % name)
    print("модулей: %d, с замечаниями: %d" % (len(names), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
