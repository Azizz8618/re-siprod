#!/usr/bin/env python3
"""Проверка собранных модулей МАДЛЕН: сколько команд получилось.

Сравнивается не код (адреса в собранном модуле свои), а число команд:
оригинальный модуль и собранный должны содержать одинаковое число
настоящих команд.  Меньше - значит компилятор что-то отбросил (чаще
всего из-за совпадающих после обрезки идентификаторов).

Использование:
    tools/siprod_code_check.py            # все модули
    tools/siprod_code_check.py SCHEMA SPAUD
"""

from __future__ import annotations

import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import siprod_madlen as sm                                # noqa: E402
from siprod_lib import Library                            # noqa: E402

# слово-заполнитель: половина слова без команды
PAD = 0o2200000


def halves(words):
    """Половины слова: команды по 20 бит в младших 40 битах слова."""
    out = []
    for w in words:
        w &= 0xFFFFFFFFFF
        out.append((w >> 20) & 0xFFFFF)
        out.append(w & 0xFFFFF)
    return out


def commands(words):
    """Число настоящих команд (без заполнителей)."""
    return sum(1 for h in halves(words) if h != PAD)


def main():
    os.makedirs(sm.WORK, exist_ok=True)
    for f in ("asm.pl", "cosy2txt", "degak.py"):
        src = os.path.join(sm.MONITOR, f)
        if os.path.exists(src) and not os.path.exists(os.path.join(sm.WORK, f)):
            shutil.copy(src, sm.WORK)
    tom_path = "/usr/local/share/besm6/" + sm.WORKVOL
    if os.path.exists(tom_path) and not os.path.exists(os.path.join(sm.WORK, sm.WORKVOL)):
        shutil.copy(tom_path, sm.WORK)
    lib = Library(os.path.join(ROOT, "siprod.bin"))
    names = sys.argv[1:] or sorted(lib.objects)
    ws = sm.read_volume(sm.WORK, sm.WORKVOL, sm.ZONE0 + 200)
    built = {}
    for name, off, h in sm.objects(ws, set(lib.objects)):
        built.setdefault(name, (off, h))
    bad = []
    for name in names:
        key = name.replace("*", "#")
        out, ok = sm.assemble(sm.WORK, key)
        if not ok:
            bad.append((name, "ошибка сборки"))
            print("%-10s ОШИБКА СБОРКИ" % name, flush=True)
            continue
        ws = sm.read_volume(sm.WORK, sm.WORKVOL, sm.ZONE0 + 200)
        built = {}
        for n2, off, h in sm.objects(ws, set(lib.objects)):
            built.setdefault(n2, (off, h))
        if key not in built:
            print("%-10s нет в томе" % name, flush=True)
            continue
        off, bh = built[key]
        s, h = lib.objects[name]
        orig = list(lib.words[s + 3:s + 3 + h["cmd"]])
        new = list(ws[bh["cmd_off"]:bh["cmd_off"] + bh["cmd"]])
        co, cn = commands(orig), commands(new)
        mark = "ok" if co == cn else "РАСХОЖДЕНИЕ"
        if co != cn:
            bad.append((name, "%d против %d" % (co, cn)))
        print("%-10s команд: оригинал %4d, собрано %4d  %s"
              % (name, co, cn, mark), flush=True)
    print("=== модулей с расхождением: %d" % len(bad))
    for n, why in bad:
        print("   ", n, why)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
