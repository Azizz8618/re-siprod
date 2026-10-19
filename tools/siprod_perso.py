#!/usr/bin/env python3
"""Запись библиотеки СИПРОДа в PERSO на дисковом томе БЭСМ-6.

Библиотека занимает подряд идущие зоны тома: первые две - каталог,
дальше - объектные модули.  Образ (24 зоны) берётся из `siprod.bin`
(это PERSO зоны 2702 тома 2248) и записывается в свободные зоны
рабочей копии тома.

Использование:
    tools/siprod_perso.py --vol=2248 --zone=3900 [--image=FILE] [--work=DIR]
"""

import argparse
import os
import shutil
import subprocess
import sys

ZONE_SIZE = 1024 * 8        # зона тома БЭСМ-6: 1024 слов по 8 байт


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vol", default="2248", help="номер тома")
    ap.add_argument("--zone", default="3900", help="начальная зона (десятичная)")
    ap.add_argument("--image", default="siprod.bin", help="образ библиотеки")
    ap.add_argument("--work", default=None,
                    help="каталог с рабочей копией тома (создаётся)")
    ap.add_argument("--path", default=None,
                    help="BESM6_PATH для besmtool (по умолчанию --work)")
    args = ap.parse_args()

    with open(args.image, "rb") as f:
        lib = f.read()
    # образ записан словами по 6 байт, зона тома - 1024 слов по 8 байт
    zones = (len(lib) // 6 + 1023) // 1024

    env = dict(os.environ)
    if args.work:
        os.makedirs(args.work, exist_ok=True)
        src = os.path.join(args.work, args.vol)
        if not os.path.exists(src):
            shutil.copy("/usr/local/share/besm6/%s" % args.vol, src)
        env["BESM6_PATH"] = args.work
    if args.path:
        env["BESM6_PATH"] = args.path

    cmd = ["besmtool", "write", args.vol, "--from-file=" + args.image,
           "--start=%s" % args.zone]
    print(" ".join(cmd))
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    if r.returncode:
        sys.exit(r.returncode)
    print("библиотека (%d зон) записана в том %s, зона %s"
          % (zones, args.vol, args.zone))


if __name__ == "__main__":
    main()
