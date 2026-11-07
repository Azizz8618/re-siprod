#!/usr/bin/env python3
"""Сборка библиотеки СИПРОД + DRAKON (Мадлен-объект) и запись на том.

Объектный модуль DRAKON (скрипт scripts/madlen_compile.py + извлечение
сырых слов) вставляется в библиотеку siprod.bin:
  * запись каталога - в конец каталога (нумерация входов не сдвигается);
  * образ модуля - за последним модулем, выровненный по 32 слова;
  * запись каталога = (дата<<26) | (длина_загрузки*8<<12).

Использование:
    python3 scripts/build_drakon_lib.py            # собрать и записать
    python3 scripts/build_drakon_lib.py --no-run   # только образ
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from siprod_lib import Library, text_encode, text_decode   # noqa: E402

SIPROD = os.path.join(ROOT, "siprod.bin")
OBJWORDS = os.path.join(HERE, "out", "drakon_obj_words.txt")
OUTDIR = os.path.join(HERE, "out")
SHARE = os.environ.get("BESM6_SHARE", "/home/z/my-project/besm6")
VOL = "2348"
PERSO_ZONE = 1088               # 0o2100 - рабочая зона PERSO


def load_len(words):
    """Длина загрузки модуля из его заголовка: cmd+const+bss."""
    w2 = words[2]
    return (w2 & 0o77777) + ((w2 >> 15) & 0o77777) + ((w2 >> 30) & 0o77777)


def main():
    run = "--no-run" not in sys.argv
    lib = Library(SIPROD)
    words = list(lib.words)

    # --- каталог: позиция завершателя -----------------------------------
    n = 1
    while True:
        nm = text_decode(words[2 * n]).rstrip()
        if not nm or not all(c.isalnum() or c in "/*" for c in nm):
            break
        n += 1
    # слова 2n,2n+1 - завершитель (пустое имя + 7777...77)

    # --- объект DRAKON ----------------------------------------------------
    obj = [int(l, 8) for l in open(OBJWORDS)]
    ll = load_len(obj)
    print("объект DRAKON: %d слов в образе, длина загрузки %d слов"
          % (len(obj), ll))

    # дата - как у самой свежей записи каталога (22 бита, биты 47..26)
    date22 = max(words[2 * i + 1] >> 26 for i in range(1, n)
                 if text_decode(words[2 * i]).rstrip())
    rec = (date22 << 26) | ((ll * 8) << 12)
    print("запись каталога: дата22=0o%o, длина*8=0o%o" % (date22, ll * 8))

    words[2 * n] = text_encode("DRAKON")
    words[2 * n + 1] = rec
    words[2 * n + 2] = 0
    words[2 * n + 3] = 0o7777777777777777

    # --- позиция образа: за последним модулем, выравнивание 32 ----------
    end = 0
    for nm, (s, h) in lib.objects.items():
        total = 3 + h["cmd"] + h["const"] + h["data"] + h["set_"] \
            + h["head"] + h["sym"] + h["long"] + h["debug"]
        end = max(end, s + total)
    pos = (end + 31) // 32 * 32
    print("последний модуль кончается на слове %d, DRAKON с слова %d"
          % (end, pos))
    if len(words) < pos + len(obj):
        words.extend([0] * (pos + len(obj) - len(words)))
    words[pos:pos + len(obj)] = obj

    out = os.path.join(OUTDIR, "lib-drakon.bin")
    os.makedirs(OUTDIR, exist_ok=True)
    with open(out, "wb") as f:
        for w in words:
            f.write((w & 0xffffffffffff).to_bytes(6, "big"))
    print("образ: %s (%d слов, %d зон)"
          % (out, len(words), -(-len(words) // 1024)))

    if not run:
        return 0

    # --- запись в рабочую копию тома -------------------------------------
    work = os.path.join(OUTDIR, "run")
    if os.path.exists(work):
        shutil.rmtree(work)
    os.makedirs(work)
    vol_path = os.path.join(work, VOL)
    shutil.copy(os.path.join(SHARE, VOL), vol_path)
    nzones = -(-len(obj) // 1024)
    env = dict(os.environ, BESM6_PATH=work + ":" + SHARE)
    r = subprocess.run(["besmtool", "write", VOL,
                        "--from-file=%s" % out, "--start=%d" % PERSO_ZONE],
                       cwd=work, env=env, capture_output=True, text=True)
    sys.stdout.write(r.stdout + r.stderr)
    if r.returncode:
        sys.exit("besmtool write failed")
    print("том: %s" % vol_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
