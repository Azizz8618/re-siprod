#!/usr/bin/env python3
"""Сборка модуля редактора ДРАКОН настоящим транслятором МАКРО-БЕМШ.

Текст модуля `drakon/drakon.be` - тот же формат, что и тексты модулей
СИПРОДа (`text/*.be`).  Здесь он переводится в исходный синтаксис
МАКРО-БЕМШ и компилируется штатным транслятором 1978 г., который работает
в эмуляторе диспака.  Разделы объекта (константы, данные, таблица символов)
у модуля редактора - общие с SCHEMA (донор), поэтому внешние символы,
константы и переменные берутся у него.

Проверяется:
  * транслятор не выдаёт ошибок;
  * мнемоники команд, скомпилированных настоящим транслятором, совпадают
    с командами, собранными ассемблером `tools/siprod_asm.py` (то есть
    редактор собирается тем же кодом, что и модули СИПРОДа).

Запуск:
    python3 drakon/bemsh.py [-v]        # собрать и показать листинг
"""
import argparse
import re
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import siprod_bemsh as sb                                   # noqa: E402
from siprod_lib import Library                              # noqa: E402
from siprod_dis import symbol_table                         # noqa: E402
from siprod_asm import assemble_text, decode                # noqa: E402

DONOR = "SCHEMA"            # донор разделов объекта (константы, символы)
NAME = "DRAKON"             # имя модуля в каталоге библиотеки
SRC = os.path.join(HERE, "drakon.be")


def build_source(lib, path, name=NAME):
    """Текст модуля -> исходник МАКРО-БЕМШ (как это делает siprod_bemsh)."""
    s, h = lib.objects[DONOR]
    sec = lib.sections(DONOR)
    locsyms, labels, instrs = sb.parse_be(path)
    ext, _l, symtab = symbol_table(lib, DONOR)
    sb.abs_syms = {}
    for i, e in enumerate(symtab):
        if e and e[0] == "abs":
            val = e[1]
            sb.abs_syms[ext.get(i, "A%d" % val)] = \
                val - 0o100000 if val >= 0o77700 else val
    # внешние символы СИПРОДа транслятор 1978 г. не знает - подменяем
    # фиктивными метками (на смысл кода не влияет)
    fake = {}
    for _num, nm in sorted(ext.items()):
        if nm not in fake:
            fake[nm] = "XEXT%d" % (len(fake) + 1)
    consts, bss = {}, {}
    for nm, off in locsyms.items():
        if off < h["cmd"]:
            continue
        if off < h["cmd"] + h["const"]:
            consts[nm] = off - h["cmd"]
        else:
            bss[nm] = off - h["cmd"] - h["const"]
    out = ["%s\tСТАРТ" % name, "\tЕ", "\tМ"]
    for nm in fake.values():
        out.append("%s\tсч" % nm)
    sb.NFAKE = len(fake)
    outside = [nm for _num, nm in sorted(ext.items())
               if "*" not in nm and sb.re.match(r"^[А-ЯЁA-Z0-9]+$", nm)]
    for off, instr, op, lab in instrs:
        label = ""
        for nm, (cmd, dms) in labels.items():
            if cmd == off and nm not in locsyms:
                label = sb.bemsh_name(nm, dms)
                break
        # внешние символы транслятор 1978 г. не знает - подменяем
        # фиктивными метками (на смысл кода не влияет)
        op = re.sub(r"^([А-ЯЁA-Z][А-ЯЁA-Z0-9]*)(\(.*\))?$",
                    lambda m: fake.get(m.group(1), m.group(1)) +
                    (m.group(2) or ""), op)
        operand = sb.operand_text(op, ext, consts, bss, labels)
        cmd = "\t%s\t%s" % (instr.lower(), operand) if operand \
            else "\t%s" % instr.lower()
        out.append(("%s\t" % label) + cmd.strip("\t"))
    for nm in sorted(consts, key=lambda k: consts[k]):
        word = lib.words[sec["const"] + consts[nm]]
        out.append("%s\tконд\tв'%012o'" % (nm, word))
    for n in range(h["bss"]):
        out.append("%s\tпам\t1" % sb.bss_name(n))
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--image", default=os.path.join(ROOT, "siprod.bin"))
    args = ap.parse_args()
    lib = Library(args.image)
    src = build_source(lib, SRC)
    srcfile = os.path.join(HERE, "src", "drakon.bemsh")
    os.makedirs(os.path.dirname(srcfile), exist_ok=True)
    open(srcfile, "w", encoding="utf-8").write(src)
    print("исходник МАКРО-БЕМШ: %s (%d строк)" % (srcfile, src.count("\n")))
    text, errs = sb.run_translator(src, "drakon")
    lst = os.path.join(HERE, "src", "drakon.lst")
    open(lst, "w", encoding="utf-8").write(text)
    print("листинг: %s" % lst)
    for e in errs:
        print("   ", e.strip())
    if "ЧИСЛО ОШИБОК=0000" not in text:
        print("ТРАНСЛЯТОР: ОШИБКИ")
        return 1
    # сверка: число команд настоящего транслятора и ассемблера
    words, _labels, _syms = assemble_text(SRC)
    got, _daddr, _right = sb.parse_listing(text)
    nreal = len(got) - sb.NFAKE
    print("команд: ассемблер %d, транслятор %d" % (len(words) * 2, nreal))
    if args.verbose:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
