#!/usr/bin/env python3
"""Поиск библиотек (формат DMS) в томах и их адреса.

Библиотека мониторной системы — это набор объектных модулей DMS: первые
две зоны — каталог (пары «имя — запись», имя в кодировке TEXT), дальше —
объектные модули.  Тома: 2248 (МД монитора и личная библиотека СИПРОДа),
2348 (пакет МГУ: ещё одна копия библиотеки СИПРОДа, системная библиотека
ФОРТРАНа и системная библиотека «Дубны»).

Запись каталога (48 бит):

| биты | что |
|---|---|
| 47..24 | дата сборки (три поля по 6 бит и запасное) |
| 23..12 | длина модуля в словах, умноженная на 8 |
| 11..0  | 0, либо длина оверлея в словах |

Адреса загрузки в записи каталога нет: модули размещаются в памяти подряд
с базового адреса библиотеки (смещение объекта в библиотеке кратно 32
словам), а база берётся из карты загрузки монитора
(tests/siprod/loadmap-dispak.txt).

Использование:
    tools/siprod_libs.py                 # все тома
    tools/siprod_libs.py --vol=2348      # один том
    tools/siprod_libs.py --vol=2248 --zone=01541
"""

import argparse
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from siprod_lib import Library, text_decode                       # noqa: E402
import siprod_bemsh as sb                                        # noqa: E402

ZONE = 1024              # слов в зоне тома
NAME_RE = re.compile(r"^[A-Za-z0-9*/]{1,8}$")
VOLUMES = ("2248", "2348")


def dump_volume(vol, work):
    """Снять образ тома (слова по 6 байт) в рабочий каталог."""
    os.makedirs(work, exist_ok=True)
    src = os.path.join(work, vol)
    if not os.path.exists(src):
        shutil.copy(os.environ.get("BESM6_SHARE", "/usr/local/share/besm6") + "/%s" % vol, src)
    out = os.path.join(work, "vol%s.bin" % vol)
    if not os.path.exists(out):
        env = dict(os.environ, BESM6_PATH=work)
        subprocess.run(["besmtool", "dump", vol, "--to-file=" + out],
                       cwd=work, env=env, capture_output=True, check=True)
    return out


def libraries(ws):
    """Библиотеки в образе: (зона, каталог, разобранная библиотека)."""
    for z in range(len(ws) // ZONE):
        for head in (0, 2):      # у некоторых библиотек есть заголовок
            start = z * ZONE + head
            ok = True
            for i in range(8):
                nm = text_decode(ws[start + 2 * i]).rstrip()
                if not nm or not NAME_RE.match(nm) or len(set(nm)) == 1:
                    ok = False
                    break
                rec = ws[start + 2 * i + 1]
                length = (rec >> 12) & 0o7777
                if length == 0 or length % 8:
                    ok = False
                    break
            if not ok:
                continue
            cat, i = [], 0
            while start + 2 * i + 1 < len(ws):
                nm = text_decode(ws[start + 2 * i]).rstrip()
                if not nm or not NAME_RE.match(nm) or len(set(nm)) == 1:
                    break
                cat.append((nm, ws[start + 2 * i + 1]))
                i += 1
            # образ библиотеки: каталог и следующие зоны (объектные
            # модули занимают больше, чем длина при загрузке)
            total = (1 + 100) * ZONE
            img = b"".join(w.to_bytes(6, "big")
                           for w in ws[z * ZONE:z * ZONE + total])
            try:
                lib = Library.__new__(Library)
                lib.data = img
                lib.nwords = len(img) // 6
                lib.words = [int.from_bytes(img[i * 6:i * 6 + 6], "big")
                             for i in range(lib.nwords)]
                lib.catalog = lib._read_catalog()
                lib.objects = lib._find_objects()
            except Exception:
                continue
            if len(lib.objects) > 2:
                yield z, cat, lib
                break


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vol", action="append", help="номер тома (по умолчанию все)")
    ap.add_argument("--work", default="/tmp/siprod-libs",
                    help="рабочий каталог")
    ap.add_argument("--zone", default=None,
                    help="только библиотека этой зоны (восьмерично)")
    args = ap.parse_args()
    lm = sb.loadmap()
    for vol in (args.vol or list(VOLUMES)):
        path = dump_volume(vol, args.work)
        data = open(path, "rb").read()
        ws = [int.from_bytes(data[i * 6:i * 6 + 6], "big")
              for i in range(len(data) // 6)]
        print("=== том %s: зон %d" % (vol, len(ws) // ZONE))
        for z, cat, lib in libraries(ws):
            if args.zone and "%04o" % z != args.zone.lstrip("0").rjust(4, "0"):
                continue
            # база библиотеки: модуль, чей адрес известен
            bases = {}
            for nm, (s, h) in lib.objects.items():
                ad = lm.get(sb.norm_name(nm))
                if ad is not None:
                    bases.setdefault(ad - s, []).append(nm)
            base = None
            if bases:
                base = max(bases.items(), key=lambda x: len(x[1]))[0]
            known = sum(1 for nm in bases for _ in bases[nm])
            print("  зона %04o: записей %d, модулей %d, база %s"
                  % (z, len(lib.catalog), len(lib.objects),
                     ("%06o" % base) if base is not None else "неизвестна"))
            print("      имена: %s" % ", ".join(sorted(lib.objects)[:8]))
            if base is not None:
                addrs = [base + s for nm, (s, h) in lib.objects.items()]
                print("      адреса модулей: %06o .. %06o (известных: %d)"
                      % (min(addrs), max(addrs), known))


if __name__ == "__main__":
    main()
