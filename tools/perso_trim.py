#!/usr/bin/env python3
"""Обрезка зоны ПЕРСО тома: оставляем только модули задачи.

После мониторной записи (`pascal/запись-2348.sh`) в зоне 0o2150 тома 2348
лежит вся библиотека задачи: копия библиотеки компилятора (из зоны 0o2570 -
она грузится оттуда и дублировать её не нужно) + новые модули РЕДАКТ и
DRАКОН.  Копия занимает ~95 зон; её обнуляем (`besmtool zero`), остаются
каталог и два модуля задачи.

Граница ищется по тексту зон: модули задачи (редактор, транслятор ДРАКОН)
записаны последними, их исходный текст виден в зоне; дубликат компилятора
видно раньше.  Код модуля может начинаться зоной раньше исходника, поэтому
зона с началом кода остаётся.

Нумерация: `besmtool view --start=N` задаёт индекс зоны в файле копии
тома, а в тексте печатается номер зоны тома (восьмерично) - номера томов
и индексы файла не совпадают (пустые зоны в выдаче не видны), поэтому
соответствие ищется просмотром зон по одной.

Использование:
    tools/perso_trim.py [--volume=2348] [--zone=2150] [--dry]
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

# маркеры в текстовой части зоны: кодировка монитора, часть букв -
# кириллические «заменители», поэтому ищем по шаблону
ED_RE = re.compile("LIS.САRD")          # символ редактора (исходник/символы)
COMP_RE = re.compile("РАSСОМРL")        # компилятор Паскаля (только в дубликате)
ADDR_RE = re.compile(r"^(\d+)\.\d+:")


def view(vol: str, index: int) -> str:
    """Текст зоны с индексом index в файле копии тома."""
    return subprocess.run(["besmtool", "view", vol, "--start=%d" % index,
                           "--length=1", "--encoding=t"],
                          capture_output=True, text=True).stdout


def zone_no(text: str):
    """Номер зоны тома (восьмерично) по выдаче."""
    for line in text.split("\n"):
        m = ADDR_RE.match(line)
        if m:
            return int(m.group(1), 8)
    return None


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

    # besmtool сам ищет том по номеру в BESM6_PATH (первая копия)
    path = os.environ.get("BESM6_PATH", "/usr/local/share/besm6")
    vol = args.volume
    if not any(d and os.path.isfile(os.path.join(d, args.volume))
               for d in path.split(":")):
        print("том %s не найден в BESM6_PATH" % args.volume, file=sys.stderr)
        return 1
    z0 = int(args.zone, 8)

    base = None
    for i in range(args.start, args.start + args.length):
        if zone_no(view(vol, i)) == z0:
            base = i
            break
    if base is None:
        print("зона 0o%o не найдена" % z0, file=sys.stderr)
        return 1

    # номера зон тома идут подряд: индекс файла = base + (номер - z0)
    f_cmp = f_ed = None
    for i in range(base + 1, base + args.length):
        text = view(vol, i)
        if f_cmp is None and COMP_RE.search(text):
            f_cmp = i
        if f_ed is None and ED_RE.search(text):
            f_ed = i
            break
    if f_ed is None:
        print("модуль редактора в зоне 0o%o не найден" % z0, file=sys.stderr)
        return 1
    if f_cmp is None:
        print("дубликата компилятора нет - обрезка не требуется", file=sys.stderr)
        return 0

    f_dup = base + 1                      # индекс первой зоны дубликата
    n = f_ed - 1 - f_dup                  # код модуля может начаться зоной раньше
    print("зона 0o%o (индекс %d): дубликат компилятора - индексы %d..%d (%d зон), "
          "модули задачи - с %d" % (z0, base, f_dup, f_dup + n - 1, n, f_ed - 1))
    if n <= 0:
        print("дубликата нет", file=sys.stderr)
        return 1
    if args.dry:
        return 0
    subprocess.run(["besmtool", "zero", args.volume,
                    "--start=%d" % f_dup, "--length=%d" % n], check=True)
    if not ED_RE.search(view(vol, f_ed)):
        print("ОШИБКА: после обрезки пропал модуль редактора", file=sys.stderr)
        return 1
    if COMP_RE.search(view(vol, f_dup)):
        print("ОШИБКА: дубликат компилятора не обнулён", file=sys.stderr)
        return 1
    print("   дубликат обнулён, модули задачи на месте")
    return 0


if __name__ == "__main__":
    sys.exit(main())
