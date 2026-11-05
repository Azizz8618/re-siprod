#!/usr/bin/env python3
"""Замена образа KLAIDA в siprod.bin на свежескомпилированный Мадленом.

Проверка гипотезы: загружается ли объект штатной компиляции МАДЛЕН,
стоящий на месте рабочего модуля.  Образ KLAIDA берётся из зоны 1408
копии тома после компиляции (scripts/out/vol или указанный каталог).

Использование: python3 scripts/swap_klaida.py <каталог_с_2348> <вых.bin>
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from siprod_lib import Library, text_decode               # noqa: E402


def read_zone_words(voldir, start, length):
    import subprocess
    out = os.path.join(voldir, "swapdump.bin")
    env = dict(os.environ, BESM6_PATH=voldir + ":" +
               os.environ.get("BESM6_SHARE", "/home/z/my-project/besm6"))
    subprocess.run(["besmtool", "dump", "2348", "--start=%d" % start,
                    "--length=%d" % length, "--to-file=" % None if False else "--to-file=" + out],
                   env=env, capture_output=True, text=True)
    d = open(out, "rb").read()
    return [int.from_bytes(d[i * 6:i * 6 + 6], "big") for i in range(len(d) // 6)]


def main():
    voldir = sys.argv[1]
    outp = sys.argv[2]
    ws = read_zone_words(voldir, 1408, 4)
    # объект KLAIDA начинается с слова 2048 зоны 1408 (как у DRAKON)
    off = 2048
    w0, w1, w2 = ws[off], ws[off + 1], ws[off + 2]
    h = dict(head=w0 & 0o7777, sym=(w0 >> 12) & 0o7777, debug=w0 >> 36,
             set=w1 & 0o77777, data=(w1 >> 15) & 0o77777, long=(w1 >> 30) & 0o77777,
             cmd=w2 & 0o77777, bss=(w2 >> 15) & 0o77777, const=(w2 >> 30) & 0o77777)
    noff = off + 3 + h["cmd"] + h["const"] + h["data"] + h["set"]
    nm = text_decode(ws[noff]).rstrip()
    end = noff + 1 + h["sym"] + h["long"]
    obj = ws[off:end]
    print("объект %r: %d слов (cmd=%d const=%d sym=%d long=%d)"
          % (nm, len(obj), h["cmd"], h["const"], h["sym"], h["long"]))

    lib = Library(os.path.join(ROOT, "siprod.bin"))
    words = list(lib.words)
    s, oh = lib.objects["KLAIDA"]
    total = 3 + oh["cmd"] + oh["const"] + oh["data"] + oh["set_"] \
        + oh["head"] + oh["sym"] + oh["long"] + oh["debug"]
    print("слот KLAIDA: слово %d, %d слов" % (s, total))
    if len(obj) > total:
        sys.exit("новый образ длиннее слота")
    words[s:s + len(obj)] = obj
    # хвост слота - нули
    for i in range(s + len(obj), s + total):
        words[i] = 0
    with open(outp, "wb") as f:
        for w in words:
            f.write((w & 0xffffffffffff).to_bytes(6, "big"))
    print("образ: %s" % outp)


if __name__ == "__main__":
    main()
