#!/usr/bin/env python3
"""Сборка модулей СИПРОДа настоящим транслятором МАКРО-БЕМШ.

Тексты `text/<модуль>.be` - это результат дизассемблирования, а не исходники:
их нельзя подать транслятору как есть.  Здесь они переводятся в исходный
синтаксис МАКРО-БЕМШ (как в проекте re-dispak) и компилируются штатным
транслятором, который работает в эмуляторе диспака.

Проверяется:
  * транслятор не выдаёт ошибок;
  * мнемоники скомпилированных команд совпадают с оригиналом;
  * ссылки на локальные метки ведут туда же, куда ведут в оригинале
    (т.е. метки в текстах стоят на нужных командах).

Ограничение: транслятор 1978 г. знает только модули ДИСПАК, поэтому
внешние символы СИПРОДа (общие блоки и вызовы других модулей) в исходнике
подменяются фиктивными метками - на смысл локальных меток это не влияет.

Запуск:
    tools/siprod_bemsh.py [МОДУЛЬ...]      # по умолчанию - все модули
    tools/siprod_bemsh.py -v МОДУЛЬ        # показать исходник и листинг
"""

import argparse
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from siprod_lib import Library                      # noqa: E402
from siprod_dis import symbol_table, sanitize     # noqa: E402
from siprod_asm import decode                      # noqa: E402

# адрес загрузки модуля в скомпилированном образе (источник без адреса)
LOAD = 1

# том, в котором лежит транслятор и личная библиотека
VOL = "2248"
TAPE = "43"                 # лента зон PERSO
WORK = os.environ.get("SIPROD_BEMSH_WORK", "/tmp/siprod-bemsh")
ZONE = os.environ.get("SIPROD_BEMSH_ZONE", "3900")

# команды МАКРО-БЕМШ, которые встречаются в модулях СИПРОДа
OPS = set("""УИ УИМ УИА УИИ СЛИ СЛИА СЧ СЧМ СЧИ СЧИМ ЗП ЗПМ МОДА МОД ПО ПЕ ПБ ПВ
РЖА РЖ СЛ ВЧ ВЧОБ И ИЛИ НТЖ ЧЕД ЦИКЛ ПИО ПИНО СДА СЛЦ ВЫПР""".split())

# разбор адресного поля команды 1-й структуры: 15 бит, биты 14..12 - признак
LOC_TAG = 0o4
SYM_TAG = 0o7


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


def ext_names(lib, name):
    """Внешние символы модуля: имя в тексте -> (имя блока, смещение).

    Имя общего блока в таблице символов DMS помечено звёздочками
    ("*LYG*"), в исходнике МАКРО-БЕМШ их не пишут.  Элемент общего блока
    задаётся как ИМЯ+СМЕЩЕНИЕ, поэтому смещение отделяется от имени.
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
                return base, off + e[2]
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
        name = base if not off else "%s+%d" % (base, off)
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
NFAKE = 0            # число фиктивных меток (вместо внешних символов)


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
    # внешние символы - объявление ВНЕШ (как в re-dispak)
    outside = sorted(set(base for base, _off in ext.values()))
    if outside:
        out.append("%s\tВНЕШ\t%s" % (name, ",".join(outside)))
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

# код команды в листинге: 1-я структура - "рег оп(2) адрес(5)",
# 2-я структура - "рег оп(3) адрес(4)"
CODE_1ST = re.compile(r"(?:^|\s)(\d{2}) (\d{2}) (\d{5})\s*$")
CODE_2ND = re.compile(r"(?:^|\s)(\d{2}) (\d{3}) (\d{4})\s*$")


def parse_listing(text):
    """Листинг транслятора -> (слова модуля, адреса данных, пункты исходника).

    Правая колонка: адрес, номер пункта, текст источника.
    Левая колонка: слова скомпилированного модуля; у слова две команды,
    вторая половина - на следующей строке.
    """
    words = []          # [(левая половина, правая половина)]
    data = []           # адреса слов данных
    right = []          # [(адрес, текст) для каждого исходного пункта]
    for line in text.splitlines():
        left = line[:RIGHT_COL]
        toks = left.split()
        if left[25:30].strip():
            # строка слова: номер слова и код его левой половины
            if len(toks) >= 3 and re.match(r"^\d{2}$", toks[-3]):
                words.append(((toks[-3], toks[-2], toks[-1]), None))
            elif len(toks) >= 2 and re.match(r"^\d{15,16}$", toks[-1]):
                data.append(int(toks[-2], 8))
        else:
            # продолжение - правая половина слова
            if len(toks) == 3 and words:
                words[-1] = (words[-1][0], (toks[0], toks[1], toks[2]))
                continue
        r = line[RIGHT_COL:].rstrip()
        m = re.match(r"^(\d{4,5})\s+(\d{4,5})\s*(.*)$", r)
        if m:
            try:
                right.append((int(m.group(1), 8), m.group(3)))
            except ValueError:
                pass
    return words, data, right


def cmd_addr_field(fields):
    """Адресное поле команды из полей листинга (1-я или 2-я структура)."""
    if not fields:
        return None
    reg, op, addr = fields
    if len(op) == 2:            # 1-я структура: бит 19 в коде операции
        return int(addr, 8)
    return int(addr, 8)


def cmd_op_field(fields):
    """Код операции команды из полей листинга."""
    if not fields:
        return None
    reg, op, addr = fields
    return int(op, 8) & 0o17 if len(op) == 2 else int(op, 8)


def check_module(lib, name, path, verbose=False):
    """Скомпилировать модуль и сравнить с оригиналом."""
    src = convert(lib, name, path)
    text, errs = run_translator(src, name.replace("*", "#"))
    if verbose:
        print(src)
        print(text[-4000:])
    errors = [e for e in errs if "НЕОП" in e or "ЗАПР" in e]
    result = dict(module=name, errors=errors, mismatch=[])
    if errors:
        return result
    # оригинал: команды и их коды
    s, h = lib.objects[name]
    code = lib.words[s + 3:s + 3 + h["cmd"]]
    locsyms, labels, instrs = parse_be(path)
    words, daddr, right = parse_listing(text)
    for off, instr, op, _lab in instrs:
        w = off // 2
        if w >= len(words):
            break
        half = words[w][1] if off % 2 else words[w][0]
        if half is None:
            continue
        orig = (code[off // 2] >> 24) if off % 2 == 0 else \
            (code[off // 2] & 0xffffff)
        # код операции и регистр должны совпадать
        dop = decode(orig)["name"]
        oop = ((orig >> 15) & 0o17) if (orig & 0x80000) else ((orig >> 12) & 0o77)
        if oop != cmd_op_field(half):
            # транслятор 1978 г. кодирует некоторые команды иначе
            result["mismatch"].append(
                "команда %d: код операции %s != %o"
                % (off, dop, cmd_op_field(half)))
        if not (orig & 0x80000):
            continue
        field = orig & 0o77777
        if (field >> 12) & 7 != LOC_TAG:
            continue        # внешний символ - транслятор решает по каталогу
        target = field & 0o7777              # смещение метки в словах
        addr = cmd_addr_field(half)
        if addr is not None and addr != (LOAD + target):
            result["mismatch"].append(
                "команда %d: ссылка на %o, метка со смещением %o -> %o"
                % (off, addr, target, LOAD + target))
        # символ раздела данных
        cand = [(nm, dms) for nm, dms in locsyms.items() if dms == target]
        if cand:
            nm = cand[0][0]
            if nm.startswith("К"):
                idx = int(nm[1:])
            else:
                idx = h["const"] + int(nm[1:])
            if idx < len(daddr) and daddr[idx] != addr:
                result["mismatch"].append(
                    "команда %d: ссылка на %o, символ %s на %o"
                    % (off, addr, nm, daddr[idx]))
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("modules", nargs="*", help="модули (по умолчанию - все)")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--image", default=os.path.join(ROOT, "siprod.bin"))
    args = ap.parse_args()
    lib = Library(args.image)
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
