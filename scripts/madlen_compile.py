#!/usr/bin/env python3
"""Компиляция drakon.madlen штатным МАДЛЕН-3.5 с записью объекта на том.

Задание повторяет asm.pl (monitor80-re) и добавляет карту *TO PERSO
(вывод Мадлен-библиотеки на том - по опыту 04.11.2026,
notes/madlen-object.md, зоны 0o2576..).  Сравнением зон тома до/после
находим, куда компилятор положил объект.

Использование:  python3 scripts/madlen_compile.py
Результат:      scripts/out/zones_before.bin, zones_after.bin,
                scripts/out/compile_run.log
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "scripts", "out")
BESM6_SHARE = os.environ.get("BESM6_SHARE", "/home/z/my-project/besm6")
DISPAK = os.environ.get("DISPAK", "dispak")
BESMTOOL = os.environ.get("BESMTOOL", "besmtool")
VOL = "2348"

JOB = """шифр 419999ЗС5^
ЛЕН 40({vol}-WR)^
ЕЕВ1А3
*NAME
*NO LIST
*MADLEN
{text}
*LIBRA:2
*TO PERSO:402600
*COPY:1,270000,600000
*STAND
*CALL DTRAN(drakon)
*EDIT
*R:1
*W:600000
*EE
*END FILE
``````
ЕКОНЕЦ
"""


def besmtool(args, path):
    env = dict(os.environ, BESM6_PATH=path)
    r = subprocess.run([BESMTOOL] + args, env=env, capture_output=True, text=True)
    if r.returncode:
        sys.exit("besmtool %s failed:\n%s%s" % (" ".join(args), r.stdout, r.stderr))
    return r.stdout


def dump_all(work, vol, out):
    return besmtool(["dump", vol, "--length=2048", "--to-file=%s" % out], work)


def main():
    os.makedirs(OUT, exist_ok=True)
    work = os.path.join(OUT, "vol")
    if os.path.exists(work):
        shutil.rmtree(work)
    os.makedirs(work)
    vol_path = os.path.join(work, VOL)
    shutil.copy(os.path.join(BESM6_SHARE, VOL), vol_path)

    text = open(os.path.join(ROOT, "drakon", "drakon.madlen"),
                encoding="utf-8").read()
    job = os.path.join(work, "job.b6")
    with open(job, "w", encoding="utf-8") as f:
        f.write(JOB.format(vol=VOL, text=text))

    before = os.path.join(OUT, "zones_before.bin")
    dump_all(work, VOL, before)

    env = dict(os.environ, BESM6_PATH=work + ":" + BESM6_SHARE)
    r = subprocess.run([DISPAK, job], cwd=work, env=env,
                       capture_output=True, text=True)
    listing = r.stdout + r.stderr
    with open(os.path.join(OUT, "compile_run.log"), "w") as f:
        f.write(listing)
    if "\n ******" in listing or "Compilation failed" in listing:
        sys.stderr.write(listing)
        sys.exit("компиляция не прошла")
    tail = [l for l in listing.splitlines() if l.strip()][-12:]
    print("хвост прогона компиляции:")
    for l in tail:
        print("   ", l)

    after = os.path.join(OUT, "zones_after.bin")
    dump_all(work, VOL, after)

    b = open(before, "rb").read()
    a = open(after, "rb").read()
    zlen = 1024 * 6
    nz = min(len(b), len(a)) // zlen
    changed = [z for z in range(nz)
               if b[z * zlen:(z + 1) * zlen] != a[z * zlen:(z + 1) * zlen]]

    def runs(zs):
        out, s, p = [], None, None
        for z in zs:
            if s is None:
                s = p = z
            elif z == p + 1:
                p = z
            else:
                out.append((s, p))
                s = p = z
        if s is not None:
            out.append((s, p))
        return out

    print("изменённых зон: %d" % len(changed))
    for s, e in runs(changed):
        print("   зоны %d (0o%o) .. %d (0o%o)" % (s, s, e, e))


if __name__ == "__main__":
    main()
