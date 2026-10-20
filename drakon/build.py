#!/usr/bin/env python3
"""Сборка библиотеки PERSO с модулем редактора ДРАКОН.

  1) ассемблирование модуля (МАКРО-БЕМШ -> объектный модуль, диспак);
  2) чтение объектного модуля из зоны тома;
  3) новая библиотека: каталог (с записью о модуле) + модули СИПРОДа + модуль
     редактора -> файл образа библиотеки;
  4) задание для запуска редактора (модуль - точка входа).

Использование:
    python3 drakon/build.py [--src ФАЙЛ.be] [--out ПРЕФИКС]
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from siprod_lib import Library, text_encode, text_decode   # noqa: E402

ZONE = 1024 * 8        # зона тома: 1024 слов по 8 байт
CAT_ZONES = 2          # каталог библиотеки - две зоны


def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.stdout:
        sys.stdout.write(r.stdout)
    if r.returncode:
        sys.stderr.write(r.stderr)
        raise SystemExit("не выполнилась: %s" % " ".join(cmd))
    return r.stdout


def assemble(src, work, load="17000"):
    """Модуль .be -> объектный модуль (слова) из зоны тома ЗП."""
    sys.path.insert(0, HERE)
    import asmjob
    job = os.path.abspath(os.path.splitext(src)[0] + ".b6")
    open(job, "w", encoding="utf-8").write(
        asmjob.make_job(src, load, "43", "01", "2222"))
    env = dict(os.environ,
               BESM6_PATH="%s:%s" % (work, "/usr/local/share/besm6"))
    out = subprocess.run(["dispak", job], capture_output=True, text=True,
                         cwd=work, env=env)
    text = out.stdout + out.stderr
    ok = False
    for l in text.splitlines():
        if "ЧИСЛО ОШ" in l:
            print("   ", l.strip())
            ok = "0000" in l
        if "НЕОП" in l or "ОПЕРАЦИИ НЕТ" in l:
            print("      ", l.strip())
    if not ok:
        raise SystemExit("ассемблирование не удалось")
    env = dict(os.environ,
               BESM6_PATH="%s:%s" % (work, "/usr/local/share/besm6"))
    tmp = os.path.join(work, "mod.bin")
    sh(["besmtool", "dump", "2222", "--start=%s" % load, "--length=1",
        "--to-file=%s" % tmp], env=env)
    data = open(tmp, "rb").read()
    return [int.from_bytes(data[i:i + 6], "big") for i in range(0, len(data), 6)]


def build_library(image, modwords, name):
    """Образ библиотеки: каталог (с новой записью) + модули + новый модуль."""
    words = [int.from_bytes(image[i * 6:(i + 1) * 6], "big")
             for i in range(len(image) // 6)]
    # 1) запись в каталог - в первое свободное место
    cat_words = CAT_ZONES * ZONE // 6
    n = 1                       # первые два слова - шапка каталога
    while 2 * n + 1 < cat_words:
        nm = text_decode(words[2 * n]).rstrip()
        if not nm or not all(c.isalnum() or c in "/*" for c in nm):
            break
        n += 1
    print("   записей в каталоге: %d, новая - №%d" % (n - 1, n - 1))
    words[2 * n] = text_encode(name)
    # запись: длина (слов*8) в битах 12..23, дата - в битах 24..47
    words[2 * n + 1] = (0o20506400 << 24) | ((len(modwords) * 8) << 12)
    # 2) модуль - в конец области модулей
    start = len(words)
    words.extend(modwords)
    print("   модуль %s: %d слов, с адреса слова %d" % (name, len(modwords),
                                                         start))
    out = bytearray()
    for w in words:
        out += w.to_bytes(6, "big")
    return bytes(out)


def job(name, lib, entry):
    """Задание для запуска модуля редактора (монитор МС Дубна)."""
    return ("ШИФР 419900ЗС5^ОЗУ 32^ТРА 100^АЦП 64^ЛЕН 67(2248)^ЕЕВ1А3\n"
            "*name\n"
            "*no lo\n"
            "*file:%s,67\n"
            "*perso:670000\n"
            "*call yesmemory\n"
            "*main %s\n"
            "*execute\n"
            "*end file\n" % (lib, entry))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(HERE, "src", "drakon.be"))
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    ap.add_argument("--name", default="DRAKON")
    ap.add_argument("--image", default=os.path.join(ROOT, "siprod.bin"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    print("1) ассемблирование", args.src)
    zp = os.path.join(args.out, "2222")     # том ЗП для объектного модуля
    if not os.path.exists(zp):
        open(zp, "wb").close()
    mod = assemble(args.src, args.out)

    print("2) сборка библиотеки")
    lib = Library(args.image)
    newimg = build_library(lib.data, mod, args.name)
    path = os.path.join(args.out, "lib.bin")
    open(path, "wb").write(newimg)
    zones = (len(newimg) // 6 + ZONE // 6 - 1) // (ZONE // 6)
    print("   образ: %d слов (%d зон) -> %s" % (len(newimg) // 6, zones, path))

    print("3) задание")
    jb = os.path.join(args.out, "drakon.b6")
    open(jb, "w", encoding="utf-8").write(job("lib.bin", "lib.bin", args.name.lower()))
    print("   ", jb)


if __name__ == "__main__":
    main()
