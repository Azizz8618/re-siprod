#!/usr/bin/env python3
"""Полная библиотека СИПРОДа для тома 2348.

На томе 2348 есть копия библиотеки СИПРОДа (зона 01267), но она
неполна: в каталоге 105 записей вместо 108, нет модулей STAATP,
STANDA и VIAPUZ, поэтому загрузчик монитора печатает «БИБЛИОТЕКА
ПОВРЕЖДЕНА» (ошибка 61).

Инструмент собирает полную библиотеку: каталог и таблица входов
берутся из зоны 2702 тома 2248 (там библиотека целая), а объектные
модули - из зоны 01267 тома 2348 и из зоны 2702 тома 2248 (для
трёх недостающих).  Готовый образ записывается в ПЕРСО тома 2348.

Использование:
    tools/siprod_vol.py --write      # собрать и записать в ПЕРСО 2348
    tools/siprod_vol.py --check      # только проверить
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from siprod_lib import Library                                # noqa: E402
from siprod_libs import libraries                             # noqa: E402

VOL = "2348"                 # том с компилятором МАДЛЕН и копией СИПРОДа
SRC_VOL = "2248"             # том с полной библиотекой СИПРОДа
# зоны в восьмеричной записи (как в отчётах по томам)
ZONE_SRC = 0o2702            # зона библиотеки СИПРОДа на томе 2248
# На боевом томе 2348 зона 0o1267 (695 дес.) с 05.11.2026 - ИСХОДНАЯ
# редакция с диска 2048.  Запись --write ведётся во временную копию тома
# (BESM6_PATH=WORK), реальные тома не изменяются.
ZONE_DST = 0o1267            # историческая целевая зона записи (0o1267)
WORK = "/tmp/siprod-vol"
IMAGE = os.path.join(ROOT, "build", "siprod-2348.bin")


def volume(vol, work):
    """Образ тома: слова по 6 байт."""
    os.makedirs(work, exist_ok=True)
    src = os.path.join(work, vol)
    if not os.path.exists(src):
        shutil.copy(os.environ.get("BESM6_SHARE", "/usr/local/share/besm6") + "/%s" % vol, src)
    out = os.path.join(work, "vol%s.bin" % vol)
    env = dict(os.environ, BESM6_PATH=work)
    subprocess.run(["besmtool", "dump", vol, "--to-file=" + out],
                   cwd=work, env=env, capture_output=True, check=True)
    data = open(out, "rb").read()
    return [int.from_bytes(data[i * 6:i * 6 + 6], "big")
            for i in range(len(data) // 6)]


def siprod_library(ws):
    """Библиотека СИПРОДа в образе тома: (зона, каталог, модули)."""
    for z, cat, lib in libraries(ws):
        if "SCHEMA" in lib.objects:
            return z, cat, lib
    return None, None, None


def build_image():
    """Образ полной библиотеки СИПРОДа (каталог + таблица входов + модули)."""
    src = volume(SRC_VOL, WORK)
    dst = volume(VOL, WORK)
    z_src, cat, lib_src = siprod_library(src)
    z_dst, _cat_dst, lib_dst = siprod_library(dst)
    if lib_src is None or lib_dst is None:
        raise SystemExit("библиотека СИПРОДа не найдена")
    # каталог (две зоны) и таблица входов - из полной копии
    head = src[z_src * 1024:z_dst * 1024] if z_dst > z_src else \
        src[z_src * 1024:z_src * 1024 + 2048]
    # объектные модули: сначала из копии на томе 2348, недостающие -
    # из полной копии на томе 2248
    order = sorted(lib_src.objects.items(), key=lambda kv: kv[1][0])
    starts = [kv[1][0] for kv in order]
    img = list(head)
    taken = set()
    for i, (name, (s, h)) in enumerate(order):
        end = starts[i + 1] if i + 1 < len(starts) else \
            s + lib_src.nwords - s
        obj = None
        if name in lib_dst.objects:
            ds, dh = lib_dst.objects[name]
            dsec = lib_dst.sections(name)
            dend = dsec["debug"] + dh["debug"]
            obj = dst[ds:dend]
        if obj is None:
            sec = lib_src.sections(name)
            obj = src[s:sec["debug"] + h["debug"]]
        taken.add(name)
        img += list(obj)
        if len(img) % 32:
            img += [0] * (32 - len(img) % 32)
    print("модулей в образе: %d, каталог: %d записей, зона %04o"
          % (len(taken), len(cat), z_src))
    return img, lib_src


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true",
                    help="записать библиотеку в ПЕРСО тома 2348")
    ap.add_argument("--out", default=IMAGE, help="куда сохранить образ")
    args = ap.parse_args()
    img, lib = build_image()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "wb") as f:
        for w in img:
            f.write(w.to_bytes(6, "big"))
    print("образ: %s (%d слов, %d зон)"
          % (args.out, len(img), (len(img) + 1023) // 1024))
    if args.write:
        work = WORK
        vol = os.path.join(work, VOL)
        if not os.path.exists(vol):
            shutil.copy(os.environ.get("BESM6_SHARE", "/usr/local/share/besm6") + "/%s" % VOL, vol)
        env = dict(os.environ, BESM6_PATH=work)
        subprocess.run(["besmtool", "write", VOL, "--from-file=" + args.out,
                        "--start=%d" % ZONE_DST],
                       cwd=work, env=env, capture_output=True, check=True)
        print("библиотека записана в ПЕРСО тома %s, зона %05o" % (VOL, ZONE_DST))
    return 0


if __name__ == "__main__":
    sys.exit(main())
