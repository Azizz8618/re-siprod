#!/usr/bin/env python3
"""Сборка модуля DRAKON (БЕМШ) в библиотеку СИПРОДа.

Рецепт загрузчика Дубны (notes/loader.md):
  каталог: длина загрузки = cmd + const + bss (ПАМ - это bss!);
  образ:   [заголовок 3 слова][cmd][const][имя][sym][long], set пуст;
  sym:     1 INS (общий блок KLAIDA), 2 INS24 (INS+030), 3 GETSTR
           (ONEPLA, позиция 37); запись каталога - в начало каталога.

Использование:
  tools/drakon_build.py LIB OUT    вставить DRAKON в библиотеку LIB -> OUT
  tools/drakon_build.py --info     только размеры модуля
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from siprod_asm import assemble_text  # noqa: E402
from siprod_lib import Library, text_decode, text_encode  # noqa: E402

SRC = os.path.join(ROOT, "drakon", "drakon.be")

# sym-элементы: (0o4000+тип)<<36 | C<<24 | D
SYM = [
    0o0000401467000033,  # 1 INS    : общий блок (KLAIDA)
    0o0000400100000030,  # 2 INS24  : INS+24
    0o0000404567000003,  # 3 GETSTR : ONEPLA (позиция 37)
]

NAME = "DRAKON"


def module_parts(path=SRC):
    """Собрать модуль: (cmd, const, bss, labels, syms)."""
    cmd, labels, syms = assemble_text(path)
    const, data = parse_cond(path)
    bss = len(data)
    return cmd, const, bss, labels, syms


def parse_cond(path=SRC):
    """КОНД/ПАМ из текста БЕМШ -> (константы, данные-нули)."""
    import re
    const, data = [], []
    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        if line.startswith("*"):
            continue
        m = re.match(r"^(\S+)\s+КОНД\s+В'(\S+)'\s*(?:,.*)?$", line)
        if m:
            val = m.group(2)
            if not re.match(r"^[0-7]{16}$", val):
                raise ValueError("КОНД %s: не 16 восьмеричных цифр" % m.group(1))
            const.append(int(val, 8))
            continue
        m = re.match(r"^(\S+)\s+ПАМ\s+(\d+)\s*(?:,.*)?$", line)
        if m:
            data.extend([0] * int(m.group(2)))
    return const, data


def build_image(name, cmd, const, bss, sym):
    """Объектный образ модуля Дубны (слова)."""
    w0 = (1 & 0o7777) | ((len(sym) & 0o7777) << 12)
    w1 = 0
    w2 = (len(cmd) & 0o77777) | ((bss & 0o77777) << 15) | \
         ((len(const) & 0o77777) << 30)
    out = [w0, w1, w2] + list(cmd) + list(const) + [text_encode(name)]
    out += list(sym)
    return out


def add_to_library(lib_path, name, cmd, const, bss, sym, out_path):
    """Вставить модуль в библиотеку; вернуть (позиция, длина загрузки)."""
    lib = Library(lib_path)
    words = list(lib.words)
    # каталог: записи с слова 2, ищем завершатель
    cat_words = 2 * 1024  # две зоны
    n = 1
    while 2 * n + 1 < cat_words:
        nm = text_decode(words[2 * n]).rstrip()
        if not nm or not all(c.isalnum() or c in "/*" for c in nm):
            break
        n += 1
    # дата - как у первой записи; запись ВСТАВЛЯЕТСЯ В НАЧАЛО каталога
    # (каталог отсортирован по убыванию дат - новая запись самая свежая)
    date = words[3] >> 24
    obj = build_image(name, cmd, const, bss, sym)
    load_len = len(cmd) + len(const) + bss
    head = words[:2]
    entries = words[2:2 * n + 2]
    term = [0, 0o7777777777777777]
    words = head + [text_encode(name), (date << 24) | ((load_len * 8) << 12)] \
        + entries + term
    end = max(s + 3 + h["cmd"] + h["const"] + h["data"] + h["set_"] +
              h["head"] + h["sym"] + h["long"] + h["debug"]
              for s, h in lib.objects.values())
    pos = (end + 31) // 32 * 32
    words.extend([0] * (pos - len(words)))
    words.extend(obj)
    buf = bytearray()
    for w in words:
        buf += (w & 0xFFFFFFFFFFFF).to_bytes(6, "big")
    open(out_path, "wb").write(bytes(buf))
    return pos, load_len


def build_library(lib_path, out_path, verbose=True):
    """Собрать библиотеку с модулем DRAKON; вернуть (позиция, длина)."""
    cmd, const, bss, labels, syms = module_parts()
    if verbose:
        print("модуль %s: команд %d слов, const %d, bss %d; загрузка %d слов"
              % (NAME, len(cmd), len(const), bss, len(cmd) + len(const) + bss))
    return add_to_library(lib_path, NAME, cmd, const, bss, SYM, out_path)


def main(argv):
    if argv and argv[0] == "--info":
        cmd, const, bss, labels, syms = module_parts()
        print("команд: %d слов" % len(cmd))
        print("const: %d слов" % len(const))
        print("bss (ПАМ): %d слов" % bss)
        print("длина загрузки: %d слов" % (len(cmd) + len(const) + bss))
        return 0
    if len(argv) != 2:
        print(__doc__)
        return 2
    lib, out = argv
    pos, load_len = build_library(lib, out)
    print("модуль %s: загрузка=%d слов | позиция %d" % (NAME, load_len, pos))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
