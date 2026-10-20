#!/usr/bin/env python3
"""Регистры и малые смещения в текстах модулей СИПРОДа (папка text).

Разбирает тексты `text/*.be` (реконструированный автокод БЕМШ) и собирает:

* по каждому регистру М1..М17 - где и в каких командах он используется,
* по каждому регистру - множество малых смещений вида `N(Мк)`,
* проверку гипотезы: являются ли малые смещения ссылками на метки
  внутри модулей (раздел данных модуля) или адресами слотов кадра.

Использование:
    tools/siprod_regs.py                 # сводка
    tools/siprod_regs.py --module SPAUD  # подробно по модулю
    tools/siprod_regs.py --json          # для внешней обработки
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from siprod_lib import Library      # noqa: E402
from siprod_asm import OPCODE_BY_NAME   # noqa: E402
from siprod_be import REG_ROLES   # noqa: E402

# мнемоники БЕМШ (из таблицы сборщика)
MNEMONICS = set(OPCODE_BY_NAME) | {"СТАРТ", "ФИНИШ"}

# роли регистров - в восьмеричной нумерации (М12 -> 0o12 = 10),
# как в шапках модулей; ROLE[10] = роль М12
ROLE = {k: v for k, v in REG_ROLES.items()}

# строка кода модуля: метка, мнемоника, операнд, комментарий
INSTR = re.compile(
    r"^\s*(?P<lab>\S+)?\s*(?P<op>[А-ЯЁ]{2,6})(?:\s+(?P<arg>\S.*?))?\s*$")


def parse_module(path):
    """Модуль -> (список команд, заголовок)."""
    txt = open(path, encoding="utf-8").read()
    cmds = []
    incode = False
    for line in txt.splitlines():
        if line.startswith("*** КОД МОДУЛЯ"):
            incode = True
            continue
        if not incode or not line.strip() or line.startswith("*"):
            continue
        code = line.split(",")[0]          # комментарий отделяется запятой
        parts = code.split()
        if not parts:
            continue
        if parts[0].upper() not in MNEMONICS:
            parts = parts[1:]              # первый токен - метка
        if not parts:
            continue
        op = parts[0].upper()
        arg = " ".join(parts[1:]) if len(parts) > 1 else ""
        cmds.append((op, arg.strip()))
    hdr = {}
    m = re.search(r"\*\s+Регистры:([^\n]*)", txt)
    if m:
        hdr["regs"] = sorted(int(x, 8) for x in re.findall(r"М(\d+)", m.group(1)))
    m = re.search(r"\*\s+Внешние:([^\n]*)", txt)
    if m:
        hdr["ext"] = m.group(1).strip()
    hdr["offs"] = {}
    for blk in re.findall(r"\*\s+Смещения в (\S+):([^\n]*)", txt):
        hdr["offs"][blk[0]] = [int(x) for x in re.findall(r"\d+", blk[1])]
    return cmds, hdr


def collect(textdir="text"):
    mods = {}
    for path in sorted(glob.glob(os.path.join(textdir, "*.be"))):
        name = os.path.basename(path)[:-3]
        cmds, hdr = parse_module(path)
        mods[name] = (cmds, hdr)
    return mods


def analyse(mods):
    reg_use = collections.defaultdict(collections.Counter)   # рег -> команда
    reg_mods = collections.defaultdict(set)                   # рег -> модули
    reg_offs = collections.defaultdict(collections.Counter)   # рег -> смещение
    mod_offs = collections.defaultdict(lambda: collections.defaultdict(set))
    for name, (cmds, hdr) in mods.items():
        for op, arg in cmds:
            for r in re.findall(r"\(М(\d+)\)", arg):
                reg_use[int(r, 8)][op] += 1
                reg_mods[int(r, 8)].add(name)
            for m in re.finditer(r"(\d+)\(М(\d+)\)", arg):
                reg_offs[int(m.group(2))][int(m.group(1))] += 1
                mod_offs[name][int(m.group(2))].add(int(m.group(1)))
        for r in hdr.get("regs", ()):
            reg_mods[r].add(name)
    return reg_use, reg_mods, reg_offs, mod_offs


def check_labels(mods, mod_offs, libpath="siprod.bin"):
    """Проверка гипотезы: смещения кадра - ссылки на метки модуля?

    Для каждого модуля сравниваются:
      * множество смещений, адресуемых через М7 (слоты кадра);
      * множество меток раздела данных модуля (V<номер> в bss).
    """
    res = []
    if not os.path.exists(libpath):
        return res
    lib = Library(libpath)
    for name, (cmds, hdr) in mods.items():
        if name not in lib.objects:
            continue
        s, h = lib.objects[name]
        frame = sorted(mod_offs[name].get(7, ()))
        # метки раздела данных: номера слов bss, доступные как V<n>
        vnums = set(range(h["bss"]))
        res.append(dict(module=name, bss=h["bss"], const=h["const"],
                        frame=frame, inside=bool(frame) and max(frame) < h["bss"],
                        eq=frame == sorted(vnums),
                        common=hdr.get("offs", {})))
    return res


def check_common(mods, libpath="siprod.bin"):
    """Проверка: "Смещения в X: n" - это ссылки на элементы общих блоков?

    Для каждого модуля объявленные в заголовке смещения сверяются с
    записями таблицы символов (тип "общий блок + смещение").
    """
    res = []
    if not os.path.exists(libpath):
        return res
    from siprod_dis import symbol_table
    lib = Library(libpath)
    for name, (cmds, hdr) in mods.items():
        if name not in lib.objects:
            continue
        ext, labels, symtab = symbol_table(lib, name)
        declared = []
        for blk, nums in hdr.get("offs", {}).items():
            for n in nums:
                declared.append(f"{blk}{n}")
        found = set(n for n in ext.values() if n)
        miss = [d for d in declared if d not in found]
        res.append(dict(module=name, declared=len(declared),
                        confirmed=len(declared) - len(miss), missing=miss))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--textdir", default="text")
    ap.add_argument("--module", help="подробно по модулю")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    mods = collect(args.textdir)
    reg_use, reg_mods, reg_offs, mod_offs = analyse(mods)

    if args.json:
        out = dict(
            regs={str(r): dict(ops=dict(reg_use[r]), mods=sorted(reg_mods[r]),
                               offs=sorted(reg_offs[r])) for r in sorted(reg_use)},
            modules={n: {str(r): sorted(v) for r, v in d.items()}
                     for n, d in mod_offs.items()})
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0

    if args.module:
        name = args.module.upper()
        if name not in mods:
            print("нет такого модуля:", name)
            return 2
        cmds, hdr = mods[name]
        print(f"== {name} ==")
        print("регистры модуля:", hdr.get("regs"))
        print("внешние:", hdr.get("ext"))
        print("смещения в общих блоках:", hdr.get("offs"))
        print("смещения по регистрам:",
              {r: sorted(v) for r, v in mod_offs[name].items()})
        for op, arg in cmds:
            if re.search(r"\(М\d+\)", arg):
                print(f"   {op:6s} {arg}")
        return 0

    print("=== регистры М1..М17 ===")
    print("%-5s %7s %7s  %-38s %s" % ("рег", "употр.", "модулей", "команды", "роль"))
    for r in sorted(reg_use):
        cmds = ", ".join(f"{k}:{v}" for k, v in reg_use[r].most_common(6))
        print("%-5s %7d %7d  %-38s %s"
              % (f"М{r:o}", sum(reg_use[r].values()), len(reg_mods[r]), cmds[:38],
                 ROLE.get(r, "")))
    print()
    print("=== малые смещения N(Мк) ===")
    for r in sorted(reg_offs):
        offs = sorted(reg_offs[r])
        print("М%-3o %4d значений: %s" % (r, len(offs), offs[:24]))
    print()
    print("=== проверка: смещения кадра (М7) и метки данных модуля ===")
    res = check_labels(mods, mod_offs)
    if not res:
        print("нет siprod.bin - проверка пропущена")
        return 0
    inside = sum(1 for x in res if x["inside"])
    print("модулей с кадром: %d,  max(смещение) < bss: %d"
          % (len(res), inside))
    print("%-10s %5s %5s  %-26s %s" % ("МОДУЛЬ", "bss", "const", "смещения М7",
                                        "внутри bss?"))
    for x in res:
        if x["frame"]:
            print("%-10s %5d %5d  %-26s %s"
                  % (x["module"], x["bss"], x["const"], x["frame"][:10],
                     "да" if x["inside"] else "нет"))
    print()
    print("=== проверка: «Смещения в X: n» - ссылки на общие блоки ===")
    com = check_common(mods)
    if not com:
        print("нет siprod.bin - проверка пропущена")
        return 0
    decl = sum(x["declared"] for x in com)
    conf = sum(x["confirmed"] for x in com)
    print("объявлено смещений: %d, подтверждено таблицей символов: %d"
          % (decl, conf))
    for x in com:
        if x["missing"]:
            print("  %-10s не найдено: %s" % (x["module"], x["missing"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
