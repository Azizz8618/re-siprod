#!/usr/bin/env python3
"""Подготовка зоны ПЕРСО тома: обнулить библиотеку зоны.

Мониторная запись (`pascal/запись-2348.sh`) переносит в зону 0o2150 всю
библиотеку задачи - вместе с копией библиотеки компилятора из зоны 0o2570.
Копия не нужна: компилятор берётся оттуда же.

Порядок работы (см. `pascal/запись-2348.sh`):

1. `tools/perso_trim.py` обнуляет библиотеку зоны 0o2150 (`besmtool zero`),
   освобождая место под модули задачи;
2. мониторная запись кладёт в зону только РЕДАКТ и ДРАКОН: для этого личная
   библиотека задачи подменяется пустой (только что обнулённой) зоной
   0o2150, а компилятор грузится из 0o2570 на время трансляции.

Использование:
    tools/perso_trim.py [--volume=2348] [--zone=2150] [--dry]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

ZONE_BYTES = 8256            # зона тома в байтах


def zone_index(vol: str, index: int) -> int:
    """Номер зоны тома (восьмерично) по индексу зоны в файле копии тома."""
    out = subprocess.run(["besmtool", "view", vol, "--start=%d" % index,
                          "--length=1", "--encoding=t"],
                         capture_output=True, text=True).stdout
    for line in out.split("\n"):
        head = line.split(":", 1)[0]
        if "." in head and head.split(".")[0].isdigit():
            return int(head.split(".")[0], 8)
    return -1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--volume", default="2348")
    ap.add_argument("--zone", default="2150",
                    help="номер зоны тома восьмерично (0o2150)")
    ap.add_argument("--start", type=int, default=1000,
                    help="индекс зоны в файле копии тома, с которого смотрим")
    ap.add_argument("--length", type=int, default=400,
                    help="сколько зон просматривать")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    path = os.environ.get("BESM6_PATH", "/usr/local/share/besm6")
    vol = args.volume
    if not any(d and os.path.isfile(os.path.join(d, args.volume))
               for d in path.split(":")):
        print("том %s не найден в BESM6_PATH" % args.volume, file=sys.stderr)
        return 1
    z0 = int(args.zone, 8)

    # индекс файла зоны 0o2150 и конец библиотеки (по свободным зонам)
    base = None
    for i in range(args.start, args.start + args.length):
        if zone_index(vol, i) == z0:
            base = i
            break
    if base is None:
        print("зона 0o%o не найдена" % z0, file=sys.stderr)
        return 1
    n = 0
    while zone_index(vol, base + n) >= 0:
        n += 1
        if n > args.length:
            break
    print("зона 0o%o: индекс %d, библиотека занимает %d зон (индексы %d..%d)"
          % (z0, base, n, base, base + n - 1))
    if n <= 0:
        print("зона пуста", file=sys.stderr)
        return 1
    if args.dry:
        return 0
    subprocess.run(["besmtool", "zero", args.volume,
                    "--start=%d" % base, "--length=%d" % n], check=True)
    # контроль: зона пуста
    if zone_index(vol, base) >= 0:
        print("ОШИБКА: зона не обнулена", file=sys.stderr)
        return 1
    print("   библиотека зоны 0o%o обнулена" % z0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
