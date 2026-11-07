#!/usr/bin/env python3
"""Извлечение Мадлен-объекта DRAKON из тома после компиляции.

После прогона компилятора МАДЛЕН (asm.pl, том 2348) собранные объекты
лежат на томе с зоны 690 (как у модулей СИПРОДа - tools/siprod_madlen.py).
Инструмент находит объект DRAKON, разбирает заголовок и печатает
сводку разделов; по --out сохраняет сырые слова (6 байт/слово).

Использование:
    python3 scripts/extract_obj.py /путь/к/копии/тома [/путь/к/2348]
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from siprod_lib import text_decode                      # noqa: E402

ZONE0 = 690                     # с этой зоны тома пишет компилятор МАДЛЕН


def read_volume(work, vol, zones):
    out = os.path.join(work, "vol.bin")
    env = dict(os.environ, BESM6_PATH=work + ":" +
               os.environ.get("BESM6_SHARE", "/home/z/my-project/besm6"))
    subprocess.run(["besmtool", "dump", vol, "--length=%d" % zones,
                    "--to-file=" + out], cwd=work, env=env,
                   capture_output=True, text=True)
    data = open(out, "rb").read()
    return [int.from_bytes(data[i * 6:i * 6 + 6], "big")
            for i in range(len(data) // 6)]


def header(ws, off):
    w0, w1, w2 = ws[off], ws[off + 1], ws[off + 2]
    return dict(head=w0 & 0o7777, sym=(w0 >> 12) & 0o7777, debug=w0 >> 36,
                set=w1 & 0o77777, data=(w1 >> 15) & 0o77777,
                long=(w1 >> 30) & 0o77777,
                cmd=w2 & 0o77777, bss=(w2 >> 15) & 0o77777,
                const=(w2 >> 30) & 0o77777, cmd_off=off + 3)


def objects(ws, known):
    out = []
    base = ZONE0 * 1024
    off = base
    while off < len(ws) - 16:
        h = header(ws, off)
        if h["head"] != 1 or not h["cmd"] or h["cmd"] > 20000:
            off += 1
            continue
        noff = h["cmd_off"] + h["cmd"] + h["const"] + h["data"] + h["set"]
        if noff < len(ws):
            name = text_decode(ws[noff]).rstrip()
            if name in known:
                out.append((name, off, h))
            off = noff + 1
            continue
        off += 1
    return out


def main():
    work = sys.argv[1] if len(sys.argv) > 1 else "/tmp/drm-work"
    vol = sys.argv[2] if len(sys.argv) > 2 else "2348"
    ws = read_volume(work, vol, 2048 - ZONE0)
    found = objects(ws, {"DRAKON"})
    if not found:
        print("объект DRAKON на томе (с зоны %d) не найден" % ZONE0)
        return 1
    for name, off, h in found:
        print("%s: слово %d (зона %d, смещение %d)"
              % (name, off, off // 1024, off % 1024))
        print("  cmd=%d const=%d data=%d bss=%d set=%d head=%d sym=%d long=%d"
              % (h["cmd"], h["const"], h["data"], h["bss"], h["set"],
                 h["head"], h["sym"], h["long"]))
        print("  длина загрузки = cmd+const+bss = %d слов"
              % (h["cmd"] + h["const"] + h["bss"]))
        noff = h["cmd_off"] + h["cmd"] + h["const"] + h["data"] + h["set"]
        print("  имя: %r" % text_decode(ws[noff]))
        if len(sys.argv) > 3 and sys.argv[3] == "--save":
            out = os.path.join(HERE, "out", "drakon_obj_words.txt")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            end = noff + 1 + h["sym"] + h["long"]
            with open(out, "w") as f:
                for w in ws[off:end]:
                    f.write("0o%016o\n" % w)
            print("  слова сохранены: %s (%d слов)" % (out, end - off))


if __name__ == "__main__":
    sys.exit(main())
