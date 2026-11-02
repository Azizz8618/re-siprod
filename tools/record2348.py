#!/usr/bin/env python3
"""Запись библиотеки СИПРОД (+ модуль ДРАКОН) на дисковый том 2348.

Образ тома берётся из прилагаемого архива disk2348.zip (файл 2348).
Библиотека записывается в PERSO тома, зона 695 (0o1267) - именно там
монитор МС "Дубна" ищет личную библиотеку СИПРОДа.

Этапы:
  1. сборка образа библиотеки: siprod.bin + объектный модуль DRAKON;
  2. рабочая копия исходного образа тома;
  3. besmtool write 2348 --from-file=<lib> --start=695;
  4. контроль записи: зоны тома читаются обратно и сличаются с образом;
  5. пуск СИПРОД (*main schema) и редактора ДРАКОН (*main drakon)
     из записанного тома (без повторной записи библиотеки).

Использование:
    python3 tools/record2348.py --source=<образ 2348> --target=<каталог>
"""
import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "drakon"))

ZONE_WORDS = 1024            # зона тома: 1024 слов
ZONE_BYTES = ZONE_WORDS * 6  # слово в образе besmtool - 6 байт (без тега)
PERSO_ZONE = 695            # 0o1267 - PERSO СИПРОДа на томе 2348


def share():
    return os.environ.get("BESM6_SHARE", "/usr/local/share/besm6")


def build_lib_with_drakon(out_path):
    """siprod.bin + объектный модуль DRAKON -> образ библиотеки."""
    from drakon.mklib import build_library          # noqa: E402
    from siprod_asm import assemble_text            # noqa: E402
    from siprod_lib import Library                  # noqa: E402

    src = os.path.join(ROOT, "drakon", "drakon.be")
    cmd, _labels, _syms = assemble_text(src)
    lib = Library(os.path.join(ROOT, "siprod.bin"))
    img = build_library(lib, "DRAKON", cmd)
    with open(out_path, "wb") as f:
        f.write(img)
    return img


def besmtool(args, path):
    env = dict(os.environ, BESM6_PATH=path)
    r = subprocess.run(["besmtool"] + args, env=env,
                       capture_output=True, text=True)
    if r.returncode:
        sys.stderr.write(r.stdout + r.stderr)
        sys.exit("besmtool %s failed" % " ".join(args))
    return r.stdout


def read_back(vol_dir, start, nzones, tmp):
    """Прочитать зоны тома обратно в файл."""
    out = os.path.join(tmp, "readback.bin")
    besmtool(["dump", "2348", "--start=%d" % start, "--length=%d" % nzones,
              "--to-file=%s" % out], vol_dir)
    return out


def compare_images(lib_path, readback_path):
    """Сличить записанный образ библиотеки с тем, что читается с тома.

    besmtool dump выдаёт слова по 6 байт подряд (зона - 6144 байта);
    сравнение - побайтовое по всей длине образа библиотеки.
    """
    lib = open(lib_path, "rb").read()
    rb = open(readback_path, "rb").read()
    if len(rb) < len(lib):
        return 0, len(lib) - len(rb), len(lib) // 6
    ok, bad = 0, 0
    for w in range(len(lib) // 6):
        want = lib[w * 6:(w + 1) * 6]
        got = rb[w * 6:(w + 1) * 6]
        if want != got:
            bad += 1
            if bad <= 5:
                print("  слово %d (зона %d): %s != %s"
                      % (w, PERSO_ZONE + w // 1024,
                         want.hex(), got.hex()))
        else:
            ok += 1
    return ok, bad, len(lib) // 6


def run_job(vol_dir, entry, inp_lines):
    """Задание dispak из записанного тома (библиотека НЕ переписывается)."""
    work = mkdtemp()
    z = "%o" % PERSO_ZONE
    lines = ["ШИФР 419900ЗС5^ОЗУ 32^ТРА 100^АЦП 64^ЛЕН 67(2348)^ЕЕВ1А3",
             "*name", "*perso:67" + z, "*call yesmemory", "*main " + entry,
             "*execute"] + inp_lines + ["*end file", "``````", "ЕКОНЕЦ"]
    job = os.path.join(work, "job.b6")
    with open(job, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    env = dict(os.environ, BESM6_PATH=vol_dir + ":" + share())
    r = subprocess.run(["dispak", job], cwd=work, env=env,
                       capture_output=True, text=True)
    out = r.stdout + r.stderr
    shutil.rmtree(work, ignore_errors=True)
    return out


def printer_only(text):
    """Только выдача на АЦПУ: между *EXECUTE и КОНЕЦ ЗАДАЧИ."""
    i = text.find("*ЕХЕСUТЕ")
    if i < 0:
        i = text.find("*EXECUTE")
    j = text.find("КОНЕЦ ЗАДАЧИ")
    return text[i + 8:j] if i >= 0 and j > i else text


def mkdtemp():
    import tempfile
    return tempfile.mkdtemp(prefix="rec2348-")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=None,
                    help="исходный образ тома 2348 (из архива disk2348.zip)")
    ap.add_argument("--target", default=None,
                    help="каталог для записанного тома")
    ap.add_argument("--lib", default=None,
                    help="готовый образ библиотеки (иначе собирается)")
    ap.add_argument("--plain", action="store_true",
                    help="записать siprod.bin без модуля DRAKON")
    ap.add_argument("--no-run", action="store_true",
                    help="не пускать задания, только записать и сличить")
    args = ap.parse_args()

    src = args.source or os.path.join(share(), "2348")
    target = args.target or os.path.join(ROOT, "..", "download", "disk2348")
    target = os.path.abspath(target)
    os.makedirs(target, exist_ok=True)
    vol = os.path.join(target, "2348")

    if not os.path.exists(vol):
        shutil.copy(src, vol)
        print("1) том-источник: %s -> %s" % (src, vol))
    else:
        print("1) записанный том уже есть: %s" % vol)

    print("2) образ библиотеки")
    lib_path = args.lib or os.path.join(target, "lib.bin")
    if not args.lib:
        if args.plain:
            shutil.copy(os.path.join(ROOT, "siprod.bin"), lib_path)
        else:
            img = build_lib_with_drakon(lib_path)
        print("   %s: %d слов (%d зон)"
              % (lib_path, os.path.getsize(lib_path) // 6,
                 -(-os.path.getsize(lib_path) // ZONE_BYTES)))
    nzones = -(-os.path.getsize(lib_path) // ZONE_BYTES)

    if not os.path.exists(os.path.join(target, ".recorded")):
        print("3) запись в PERSO тома 2348, зона %d (0o%o)"
              % (PERSO_ZONE, PERSO_ZONE))
        out = besmtool(["write", "2348", "--from-file=%s" % lib_path,
                        "--start=%d" % PERSO_ZONE], target)
        sys.stdout.write(out)
        open(os.path.join(target, ".recorded"), "w").write("ok\n")
    else:
        print("3) запись уже выполнена (файл .recorded)")

    print("4) контроль записи")
    tmp = mkdtemp()
    rb = read_back(target, PERSO_ZONE, nzones, tmp)
    ok, bad, nwords = compare_images(lib_path, rb)
    print("   слов сверено: %d, совпало: %d, расходится: %d"
          % (nwords, ok, bad))
    if bad:
        sys.exit("контроль записи не пройден")
    shutil.rmtree(tmp, ignore_errors=True)

    if args.no_run:
        return
    print("5) пуск из записанного тома (библиотека не переписывается)")
    probe = ["*RED", "*RG*RU", "*/*DЗАПИСЬ НА ДИСК 2348",
             "*/*DСИПРОД+ДРАКОН", "*E", "*END"]
    out = run_job(target, "schema", probe)
    body = printer_only(out)
    print("   *main schema: %s"
          % ("СИПРОД печатает" if "ЗАПИСЬ НА ДИСК 2348" in body
             else "ОШИБКА: выдачи нет"))
    if "ЗАПИСЬ НА ДИСК 2348" not in body:
        print(body[:800])
        sys.exit("СИПРОД из записанного тома не заработал")

    out = run_job(target, "drakon",
                  ["ЗАГОЛОВОК ПРОВЕРКА", "ВЕТКА ПЕРВАЯ",
                   "ДЕЙСТВИЕ ЧТО-ТО СДЕЛАТЬ", ""])
    tail = out[-400:]
    print("   *main drakon: модуль отработал и вернулся в монитор"
          if "КОНЕЦ ЗАДАЧИ" in out else "   *main drakon: НЕТ КОНЦА ЗАДАЧИ")
    if "КОНЕЦ ЗАДАЧИ" not in out:
        print(tail)
        sys.exit("модуль DRAKON не вернулся в монитор")
    print("\nГотово: том %s записан и проверен" % vol)


if __name__ == "__main__":
    main()
