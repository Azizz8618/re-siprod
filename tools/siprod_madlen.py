#!/usr/bin/env python3
"""Модули СИПРОДа в автокоде МАДЛЕН: разбор, сборка и проверка.

Три шага:

1. **разбор** - дизассемблером dtran (https://github.com/besm6/dtran) в
   формат МАДЛЕН (макроязык Монитор-80); результат - в каталоге
   `madlen-gen/` (он перезаписывается при каждом разборе);
2. **сборка** - штатным компилятором МАДЛЕН мониторной системы
   (`monitor80-re/tools/asm.pl`, том 2348 - там компилятор МАДЛЕН);
   собираются **откомментированные** тексты из каталога `madlen/` - они
   наполнены пояснениями и при разборе не перезаписываются;
3. **проверка** - библиотека собирается заново: разделы команд модулей
   берутся из собранных модулей, остальное - из исходной библиотеки
   СИПРОДа; СИПРОД с такой библиотекой запускается и его вывод
   сравнивается с эталонным (`tests/siprod/cases/*.out`).

Формат объектного модуля у компилятора МАДЛЕН мониторный (таблица точек
входа и «упакованный» заголовок на 10 слов), у библиотеки СИПРОДа -
«Дубна» («распакованный» заголовок на 3 слова), поэтому для проверки
берутся только команды модулей, а остальные разделы - из исходной
библиотеки.

Использование:
    tools/siprod_madlen.py                    # разбор всех модулей -> madlen-gen/
    tools/siprod_madlen.py --check            # сборка из madlen/ и проверка
    tools/siprod_madlen.py --check --keep     # ... с сохранением образа

Каталог `madlen/` (откомментированные тексты) инструмент не трогает:
перезаписывается только `madlen-gen/`.
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
from siprod_lib import Library, text_decode                       # noqa: E402

DTRAN = os.environ.get("SIPROD_DTRAN", "dtran")
ASMPL = "/home/azizz/Yandex.Disk/monitor80-re/tools/asm.pl"
MONITOR = "/home/azizz/Yandex.Disk/monitor80-re/tools"
WORKVOL = "2348"          # том с компилятором МАДЛЕН
WORK = "/tmp/siprod-madlen"
SRC = [os.path.join(ROOT, "madlen")]        # откомментированные тексты
ZONE0 = 690               # с этой зоны тома пишет компилятор МАДЛЕН


def find_dtran(path=None):
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


def env(work=WORK, vol=WORKVOL):
    e = dict(os.environ)
    e["BESM6_PATH"] = work + ":/usr/local/share/besm6"
    e["WORKVOL"] = vol
    e["PATH"] = work + ":" + e["PATH"]
    return e


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
    return "\n".join(l for l in r.stdout.splitlines() if not l.startswith("C ")) + "\n"


def assemble(work, name):
    """Собрать модуль компилятором МАДЛЕН; вернуть (текст сборки, ok)."""
    masm = os.path.join(work, name.replace("*", "#") + ".masm")
    shutil.copy(os.path.join(SRC[0], name.replace("*", "#") + ".madlen"), masm)
    r = subprocess.run(["perl", "-CA", ASMPL, masm], cwd=work,
                       capture_output=True, text=True, env=env(work))
    out = r.stdout + r.stderr
    return out, "*****" not in out


def read_volume(work, vol, zones):
    out = os.path.join(work, "vol.bin")
    subprocess.run(["besmtool", "dump", vol, "--length=%d" % zones,
                    "--to-file=" + out], cwd=work, env=env(work),
                   capture_output=True)
    data = open(out, "rb").read()
    return [int.from_bytes(data[i * 6:i * 6 + 6], "big")
            for i in range(len(data) // 6)]


def header(ws, off):
    """Заголовок объектного модуля (распакованный) - как в библиотеке."""
    w0, w1, w2 = ws[off], ws[off + 1], ws[off + 2]
    return dict(head=w0 & 0o7777, sym=(w0 >> 12) & 0o7777, debug=w0 >> 36,
                set=w1 & 0o77777, data=(w1 >> 15) & 0o77777,
                long=(w1 >> 30) & 0o77777,
                cmd=w2 & 0o77777, bss=(w2 >> 15) & 0o77777,
                const=(w2 >> 30) & 0o77777, cmd_off=off + 3)


def objects(ws, known):
    """Собранные модули: (имя, смещение, заголовок)."""
    out = []
    base = ZONE0 * 1024
    for off in range(base, len(ws) - 16, 32):
        h = header(ws, off)
        if h["head"] != 1 or not h["cmd"] or h["cmd"] > 20000:
            continue
        noff = h["cmd_off"] + h["cmd"] + h["const"] + h["data"] + h["set"]
        if noff >= len(ws):
            continue
        name = text_decode(ws[noff]).rstrip()
        if name in known:
            out.append((name, off, h))
    return out


def build_library(lib, ws, built, out):
    """Библиотека: каталог и таблица входов - из исходной, команды - из
    собранных модулей."""
    order = sorted(lib.objects.items(), key=lambda kv: kv[1][0])
    starts = [kv[1][0] for kv in order]
    img = list(lib.words[:starts[0]])      # каталог + таблица входов
    same = diff = 0
    for i, (name, (s, h)) in enumerate(order):
        end = starts[i + 1] if i + 1 < len(starts) else lib.nwords
        obj = list(lib.words[s:end])
        key = name.replace("*", "#")
        if key in built:
            off, bh = built[key]
            if bh["cmd"] == h["cmd"]:
                new = ws[bh["cmd_off"]:bh["cmd_off"] + bh["cmd"]]
                if new == obj[3:3 + h["cmd"]]:
                    same += 1
                    obj[3:3 + h["cmd"]] = new
                else:
                    diff += 1
        img += obj
    with open(out, "wb") as f:
        for w in img:
            f.write(w.to_bytes(6, "big"))
    return same, diff


def check(work, lib, image):
    """Запустить СИПРОД с библиотекой и сравнить вывод с эталоном."""
    cases = os.path.join(ROOT, "tests/siprod/cases")
    vol = os.path.join(work, "2248")
    shutil.copy("/usr/local/share/besm6/2248", vol)
    subprocess.run(["besmtool", "write", "2248", "--from-file=" + image,
                    "--start=02702"], cwd=work, env=env(work),
                   capture_output=True)
    bad = 0
    total = 0
    for t in sorted(os.listdir(cases)):
        if not t.endswith(".txt"):
            continue
        total += 1
        exp = os.path.join(cases, t[:-4] + ".out")
        r = subprocess.run([os.path.join(ROOT, "tests/siprod/run.sh"),
                            os.path.join(cases, t)], capture_output=True,
                           text=True, env=env(work))
        if open(exp, encoding="utf-8").read().strip() != r.stdout.strip():
            print("   FAIL %s" % t)
            bad += 1
    return total, bad


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("modules", nargs="*", help="модули (по умолчанию - все)")
    ap.add_argument("--out", default=os.path.join(ROOT, "madlen-gen"),
                    help="каталог для результата разбора")
    ap.add_argument("--src", default=os.path.join(ROOT, "madlen"),
                    help="каталог с откомментированными текстами (сборка)")
    ap.add_argument("--image", default=os.path.join(ROOT, "siprod.bin"))
    ap.add_argument("--dtran", default=None, help="путь к дизассемблеру dtran")
    ap.add_argument("--check", action="store_true",
                    help="собрать модули компилятором МАДЛЕН и проверить")
    ap.add_argument("--keep", action="store_true",
                    help="сохранить образ собранной библиотеки")
    args = ap.parse_args()
    SRC[0] = args.src
    dtran = find_dtran(args.dtran)
    if not dtran:
        print("не найден дизассемблер dtran (укажите --dtran=)",
              file=sys.stderr)
        return 2
    os.makedirs(args.out, exist_ok=True)
    lib = Library(args.image)
    names = args.modules or sorted(lib.objects)
    for name in names:
        if name not in lib.objects:
            print("нет модуля: %s" % name, file=sys.stderr)
            continue
        text = disassemble(dtran, object_image(lib, name), args.out, name)
        p = os.path.join(args.out, name.replace("*", "#") + ".madlen")
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        print("%-10s -> %s" % (name, os.path.relpath(p, ROOT)))
    if not args.check:
        return 0
    # сборка компилятором МАДЛЕН
    os.makedirs(WORK, exist_ok=True)
    for f in ("asm.pl", "cosy2txt", "degak.py"):
        src = os.path.join(MONITOR, f)
        if os.path.exists(src) and not os.path.exists(os.path.join(WORK, f)):
            shutil.copy(src, WORK)
    shutil.copy("/usr/local/share/besm6/" + WORKVOL,
                os.path.join(WORK, WORKVOL))
    bad = []
    for name in names:
        out, ok = assemble(WORK, name)
        if not ok:
            bad.append(name)
    print("собрано компилятором МАДЛЕН: %d, с ошибками: %d"
          % (len(names), len(bad)))
    for n in bad:
        print("   %s" % n)
    if bad:
        return 1
    ws = read_volume(WORK, WORKVOL, ZONE0 + 200)
    built = {}
    for name, off, h in objects(ws, set(lib.objects)):
        built.setdefault(name, (off, h))
    image = os.path.join(WORK, "siprod-madlen.bin")
    same, diff = build_library(lib, ws, built, image)
    print("модулей с совпавшим кодом: %d, код оставлен исходный: %d"
          % (same, diff))
    total, bad = check(WORK, lib, image)
    print("проверка СИПРОДа: случаев %d, несовпавших %d" % (total, bad))
    if args.keep:
        shutil.copy(image, os.path.join(ROOT, "build", "siprod-madlen.bin"))
        print("образ сохранён: build/siprod-madlen.bin")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
