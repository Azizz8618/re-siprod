#!/usr/bin/env python3
"""Трассировка ссылок на данные модуля СИПРОДа.

Показывает, где используется каждый элемент данных модуля и что с ним
делается: для каждой ссылки печатается команда и следующие команды
блока (с пояснениями из текста МАДЛЕН).  Так видно, с чем константа
сравнивается и какую роль играет.

Использование:
    tools/siprod_trace.py МОДУЛЬ [--ctx N] [--only ПОДСТРОКА]
                                 [--kind ЧИСЛА/КОМАНДЫ/...]

Пример:
    tools/siprod_trace.py SCHEMA --kind ЧИСЛА --ctx 8
"""

from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from siprod_data_sections import group_of                  # noqa: E402
from siprod_lib import Library                            # noqa: E402
import siprod_data as sd                                  # noqa: E402

IMAGE = os.path.join(ROOT, "siprod.bin")
MAD = os.path.join(ROOT, "madlen")

# объявление данных: " ИМЯ:,INT,1" / " ИМЯ:,BSS,4" / " ,INT,3"
DECL_RE = re.compile(r"^\s*(?:([A-Za-zА-ЯЁ*][A-Za-zА-ЯЁ0-9_+*]*)?:)?,?"
                     r"(BSS|ISO|INT|LOG|OCT|HEX|BIN)(?:,(.*))?$")
# команды МАДЛЕН
CMD_RE = re.compile(r"^\s*(?:([A-Za-zА-ЯЁ*][A-Za-zА-ЯЁ0-9_+*]*):)?"
                     r"([0-9]+|M[0-9]+)?,([A-Z0-9/+*-]+),?(.*)$")
# ссылка на данные: "КОНСТАНТА+662" / "ПЕРЕМЕННАЯ+712"
REF_RE = re.compile(r"^([A-Za-zА-ЯЁ][A-Za-zА-ЯЁ0-9_]*)(?:\+([0-7]+))?$")

# операции МАДЛЕН (для отделения команд от объявлений)
OPS = set("""UTC XTA NTR ITS VTM ATX UJ VJM A+X AEX UZA A-X STI U1A WTC
X-A MTJ STX UTM ATI AOX XTS AAX ASN ITA VZM VLM V1M ARX ASX A/X A*X E-N
E+N SUBP""".split())


def built_items(path):
    """Объявления данных собранного текста: [(имя, тип, значение)]."""
    out = []
    for line in open(path, encoding="utf-8"):
        st = line.rstrip()
        m = DECL_RE.match(st.strip())
        if m:
            out.append((m.group(1), m.group(2), (m.group(3) or "").strip()))
    return out


def st_is_comment(line):
    return line.lstrip().startswith("C")


def collect(module):
    """Элементы данных модуля: {слово: (имя, тип, значение)} + строки кода."""
    path = os.path.join(MAD, module.replace("*", "#") + ".madlen")
    if not os.path.exists(path):
        return None, None
    items = sd.data_items(module)          # (слово, имя, тип, значение)
    decls = built_items(path)
    table = {}
    for i, (word, _raw, kind, val) in enumerate(items):
        if word is None or i >= len(decls):
            continue
        name = decls[i][0] or ("СЛОВО_%o" % word)
        table[word] = (name, kind, val)
    lines = open(path, encoding="utf-8").read().splitlines()
    return table, lines


def parse_cmd(line):
    """Строка команды: (отступ, метка, регистр, операция, операнд, комментарий)."""
    if st_is_comment(line) or not line.strip():
        return None
    body = line.rstrip()
    comment = ""
    if len(body) > 39:
        head, tail = body[:39], body[39:]
        if tail.lstrip().startswith("."):
            comment = tail.strip()
            body = head.rstrip()
    parts = body.split(",")
    if len(parts) < 3:
        return None
    lab = parts[0].strip()
    op = parts[1].strip()
    if op not in OPS:
        return None
    operand = parts[2].strip() if len(parts) > 2 else ""
    return lab, op, operand, comment


def show_calls(cmds, table, args):
    """Параметры, передаваемые каждому вызову:Push значений со стека."""
    pushes = []
    for k, (_i, lab, op, operand, cmt) in enumerate(cmds):
        if op == "VTM":
            m = REF_RE.match(operand)
            word = None
            if m and m.group(1) in ("КОНСТАНТА", "ПЕРЕМЕННАЯ"):
                word = int(m.group(2), 8) if m.group(2) else 0
            nxt = cmds[k + 1] if k + 1 < len(cmds) else None
            if word is not None and nxt and nxt[2] == "ITS":
                name, kind, val = table.get(word, ("СЛОВО_%o" % word, "", ""))
                pushes.append((name, kind, val, word))
        elif op == "VJM":
            target = operand.strip()
            if args.only and args.only not in target:
                continue
            tail = pushes[-args.params:]
            print("вызов %-12s параметры: %s" % (
                target,
                ", ".join("%s=%s" % (n, (v or "").split(".")[0].strip())
                          for n, _k, v, _w in tail) or "-"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("module")
    ap.add_argument("--ctx", type=int, default=6,
                    help="сколько команд показывать после ссылки")
    ap.add_argument("--only", default=None,
                    help="показывать только элементы с таким именем")
    ap.add_argument("--kind", default=None,
                    help="показывать только элементы этой группы данных")
    ap.add_argument("--all", action="store_true",
                    help="показывать и неиспользуемые элементы")
    ap.add_argument("--calls", action="store_true",
                    help="показать параметры каждого вызова")
    ap.add_argument("--params", type=int, default=8,
                    help="сколько последних параметров показывать")
    args = ap.parse_args()

    lib = Library(IMAGE)
    module = args.module
    table, lines = collect(module)
    if table is None:
        print("нет текста МАДЛЕН для модуля %s" % module)
        return 1

    # ссылки: слово -> [(номер строки, операнд, операция)]
    refs = {}
    cmds = []
    for idx, line in enumerate(lines):
        cmd = parse_cmd(line)
        if cmd is None:
            continue
        lab, op, operand, comment = cmd
        cmds.append((idx, lab, op, operand, comment))
        m = REF_RE.match(operand.split(".")[0].strip())
        if not m:
            continue
        base, off = m.group(1), m.group(2)
        if base not in ("КОНСТАНТА", "ПЕРЕМЕННАЯ"):
            continue
        word = int(off, 8) if off else 0
        refs.setdefault(word, []).append((idx, operand, op))

    if args.calls:
        show_calls(cmds, table, args)
        return 0

    for word in sorted(table):
        name, kind, val = table[word]
        if args.only and args.only not in name:
            continue
        g = group_of(name, kind, val)
        if args.kind and args.kind != g:
            continue
        used = refs.get(word, [])
        if not used and not args.all:
            continue
        body = (val or "").split(".")[0].strip()
        print("=== слово %d (0o%o) %s %s = %r   [%s]"
              % (word, word, kind, name, body, g))
        for idx, operand, op in used:
            kind_ref = ("  [индексированная]" if "." in operand
                        else "")
            print("   ссылка: %s%s" % (operand, kind_ref))
            k = cmds.index(next(c for c in cmds if c[0] == idx))
            for j in range(k, min(k + args.ctx, len(cmds))):
                _i, lab, o, opnd, cmt = cmds[j]
                mark = ">>" if j == k else "  "
                print("     %s %-6s %-22s %s"
                      % (mark, o, opnd[:22], cmt[:60]))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
