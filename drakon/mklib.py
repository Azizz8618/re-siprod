#!/usr/bin/env python3
"""Сборка библиотеки PERSO с модулем редактора ДРАКОН.

Библиотека СИПРОДа (личная библиотека тома 2248) состоит из каталога
(две зоны) и объектных модулей, идущих следом.  Модуль редактора
добавляется в конец: запись в каталоге + образ объекта.

Объект нового модуля собирается по образцу RINT: те же внешние символы
(SYTOBI, KONSTA, SYTOBI1..5) и тот же раздел констант, свой код и
своё имя.

Использование:
    python3 drakon/mklib.py [--src drakon/drakon.be] [--out drakon/out]
"""
import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from siprod_lib import Library, text_encode, text_decode     # noqa: E402
from siprod_asm import assemble_text                          # noqa: E402

DONOR = "SCHEMA"      # образец объекта (таблица символов)
ZONE = 1024 * 8          # зона тома: 1024 слов по 8 байт
CAT_ZONES = 2            # каталог библиотеки - две зоны
M12, M15 = 0o7777, 0o77777


def object_words(lib, donor, name, cmd, head_len=1, debug_len=0):
    """Образ объектного модуля: разделы по образцу donor."""
    s, h = lib.objects[donor]
    sec, p = {}, s + 3
    for nm, ln in (("cmd", h["cmd"]), ("const", h["const"]), ("data", h["data"]),
                   ("set", h["set_"]), ("head", h["head"]), ("sym", h["sym"]),
                   ("long", h["long"]), ("debug", h["debug"])):
        sec[nm] = p
        p += ln
    const = lib.words[sec["const"]:sec["const"] + h["const"]]
    data = lib.words[sec["data"]:sec["data"] + h["data"]]
    set_ = lib.words[sec["set"]:sec["set"] + h["set_"]]
    sym = lib.words[sec["sym"]:sec["sym"] + h["sym"]]
    long_ = lib.words[sec["long"]:sec["long"] + h["long"]]
    # заголовок: длины разделов
    w0 = (head_len & M12) | ((len(sym) & M12) << 12) | ((debug_len & M15) << 36)
    w1 = ((len(set_)) & M15) | ((len(data) & M15) << 15) | \
         ((len(long_)) & M15) << 30
    w2 = ((len(cmd)) & M15) | (0 << 15) | ((len(const)) & M15) << 30
    out = [w0, w1, w2] + list(cmd) + list(const) + list(data) + list(set_)
    out.append(text_encode(name))
    out += list(sym) + list(long_)
    return out, len(cmd) + len(const)


def build_library(lib, name, cmd):
    """Новая библиотека: каталог (+ запись) + модули + новый модуль."""
    words = list(lib.words)
    cat_words = CAT_ZONES * ZONE // 6
    n = 1                                  # первые два слова - шапка каталога
    while 2 * n + 1 < cat_words:
        nm = text_decode(words[2 * n]).rstrip()
        if not nm or not all(c.isalnum() or c in "/*" for c in nm):
            break
        n += 1
    print("   записей в каталоге: %d" % (n - 1))
    obj, load_len = object_words(lib, DONOR, name, cmd)
    # новая запись вставляется на место завершателя каталога,
    # завершатель сдвигается за ней
    print("   завершатель каталога: слова %d,%d" % (2 * n, 2 * n + 1))
    words[2 * n] = text_encode(name)
    # в записи каталога - длина ЗАГРУЗКИ модуля (cmd+const+bss) в словах*8
    # дата записи - как у самой свежей записи каталога: модуль должен быть
    # не старше библиотеки (иначе загрузчик отвергает программу)
    # дата записи: берётся у соседней записи (загрузчик отвергает
    # модуль, если дата записи не совпадает с принятой в библиотеке)
    dates = [words[2 * i + 1] >> 24 for i in range(1, n)
             if text_decode(words[2 * i]).rstrip()]
    date = max(dates) if dates else 0
    date = dates[96] if len(dates) > 96 else date
    words[2 * n + 1] = (date << 24) | ((load_len * 8) << 12)
    print("   дата записи: %o, длина загрузки: %d слов" % (date, load_len))
    # завершатель каталога - за новой записью
    words[2 * n + 2] = 0
    words[2 * n + 3] = 0o7777777777777777
    # модули размещаются подряд, выровненные по 32 слова; каталог -
    # первые пять зон образа
    end = 0
    for s_, h_ in lib.objects.values():
        total = 3 + h_["cmd"] + h_["const"] + h_["data"] + h_["set_"] + \
                h_["head"] + h_["sym"] + h_["long"] + h_["debug"]
        end = max(end, s_ + total)
    pos = (end + 31) // 32 * 32
    print("   последний модуль заканчивается на слове %d, новый - с %d"
          % (end, pos))
    words.extend([0] * (pos - len(words)))
    words.extend(obj)
    out = bytearray()
    for w in words:
        out += (w & 0xffffffffffff).to_bytes(6, "big")
    return bytes(out)


def job(entry, inp, zone):
    """Задание для запуска модуля редактора (монитор МС Дубна).

    Библиотека лежит на томе 2248 (рабочая копия), зона zone - восьмеричная.
    """
    return ("ШИФР 419900ЗС5^ОЗУ 32^ТРА 100^АЦП 64^ЛЕН 67(2248)^ЕЕВ1А3\n"
            "*name\n"
            "*no lo\n"
            "*perso:67%o\n"
            "*call yesmemory\n"
            "*main %s\n"
            "*execute\n" % (zone, entry)) + inp + "*end file\n``````\nЕКОНЕЦ\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(HERE, "drakon.be"))
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    ap.add_argument("--name", default="DRAKON")
    ap.add_argument("--image", default=os.path.join(ROOT, "siprod.bin"))
    ap.add_argument("--inp", default=None, help="файл входного потока")
    ap.add_argument("--zone", type=int, default=3900,
                    help="зона тома 2248 для библиотеки (десятичная)")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    print("1) сборка модуля", args.src)
    cmd, labels, syms = assemble_text(args.src)
    print("   команд: %d, символов: %d" % (len(cmd), len(syms)))

    print("2) сборка библиотеки")
    lib = Library(args.image)
    img = build_library(lib, args.name, cmd)
    path = os.path.join(args.out, "lib.bin")
    open(path, "wb").write(img)
    zones = (len(img) // 6 + ZONE // 6 - 1) // (ZONE // 6)
    print("   образ: %d слов (%d зон) -> %s" % (len(img) // 6, zones, path))

    print("3) запись библиотеки в рабочую копию тома 2248")
    vol = os.path.join(args.out, "2248")
    if not os.path.exists(vol):
        shutil.copy("/usr/local/share/besm6/2248", vol)
    env = dict(os.environ, BESM6_PATH="%s:%s" % (args.out,
                                                 "/usr/local/share/besm6"))
    subprocess.run(["besmtool", "write", "2248", "--from-file=%s" % path,
                    "--start=%d" % args.zone], env=env, check=True)
    print("   том %s, зона %d (0o%o)" % (vol, args.zone, args.zone))

    print("4) задание")
    inp = ""
    if args.inp:
        inp = open(args.inp, encoding="utf-8").read()
    jb = os.path.join(args.out, "drakon.b6")
    open(jb, "w", encoding="utf-8").write(job(args.name.lower(), inp, args.zone))
    print("   ", jb)


if __name__ == "__main__":
    main()
