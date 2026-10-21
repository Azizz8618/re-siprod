#!/usr/bin/env python3
"""Дизассемблирование СИПРОДа в автокод МАДЛЕН (дизассемблером dtran).

МАДЛЕН - макроязык мониторной системы Монитор-80; исходники на нём
(`monitor80-re/permanent/*.asm`) читаются в алфавите мониторной системы
(ГОСТ 10859), а имена в библиотеке СИПРОДа записаны в кодировке TEXT
системы «Дубна».  Дизассемблер dtran (https://github.com/besm6/dtran)
разбирает объектные модули DMS и печатает их в формате МАДЛЕН сам,
с правильными именами.

Каждый модуль библиотеки вынимается в отдельный файл формата DMS и
разбирается dtran; результат - в каталоге `madlen/`.

Использование:
    tools/siprod_madlen.py                    # все модули -> madlen/
    tools/siprod_madlen.py SCAN SPAUD         # только указанные
    tools/siprod_madlen.py --out=dir         # другой каталог
    tools/siprod_madlen.py --dtran=/путь     # где искать dtran
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from siprod_lib import Library                                  # noqa: E402

DTRAN = os.environ.get("SIPROD_DTRAN", "dtran")


def find_dtran(path=None):
    """Путь к дизассемблеру dtran."""
    if path:
        return path
    found = shutil.which("dtran")
    if found:
        return found
    for p in ("/home/azizz/Yandex.Disk/dtran/dtran",
              "/home/azizz/Yandex.Disk/monitor80-re/dtran/dtran"):
        if os.path.exists(p):
            return p
    return None


def object_image(lib, name):
    """Объектный модуль библиотеки (формат DMS) - без раздела комментария."""
    s, h = lib.objects[name]
    sec = lib.sections(name)
    end = sec["debug"] + h["debug"]
    return b"".join(w.to_bytes(6, "big") for w in lib.words[s:end])


def disassemble(dtran, image, work, name):
    """Разобрать объектный модуль dtran'ом; вернуть текст."""
    src = os.path.join(work, name.replace("*", "#") + ".dms")
    with open(src, "wb") as f:
        f.write(image)
    r = subprocess.run([dtran, "-F", "dms", src], capture_output=True, text=True)
    out = r.stdout
    # dtran печатает в служебные строки (C ...) - их убираем
    lines = [l for l in out.splitlines() if not l.startswith("C ")]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("modules", nargs="*", help="модули (по умолчанию - все)")
    ap.add_argument("--out", default=os.path.join(ROOT, "madlen"),
                    help="каталог для результата")
    ap.add_argument("--image", default=os.path.join(ROOT, "siprod.bin"))
    ap.add_argument("--dtran", default=None, help="путь к дизассемблеру dtran")
    args = ap.parse_args()
    dtran = find_dtran(args.dtran)
    if not dtran:
        print("не найден дизассемблер dtran (укажите --dtran=)",
              file=sys.stderr)
        return 2
    os.makedirs(args.out, exist_ok=True)
    lib = Library(args.image)
    names = args.modules or sorted(lib.objects)
    with tempfile.TemporaryDirectory() as work:
        for name in names:
            if name not in lib.objects:
                print("нет модуля: %s" % name, file=sys.stderr)
                continue
            text = disassemble(dtran, object_image(lib, name), work, name)
            p = os.path.join(args.out, name.replace("*", "#") + ".madlen")
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
            print("%-10s -> %s" % (name, os.path.relpath(p, ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
