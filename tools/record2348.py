#!/usr/bin/env python3
"""Запись библиотеки СИПРОД (+ модуль ДРАКОН) на дисковый том 2348.

Сценарий самостоятельной записи: образ тома берётся из прилагаемого
архива disk2348.zip (файл tmp/2348) или готового образа, библиотека
собирается из репозитория и пишется в PERSO тома, зона 695 (0o1267) -
именно там монитор МС "Дубна" ищет личную библиотеку СИПРОДа.

Этапы:
  1. том: копия исходного образа (или запись прямо в него при --in-place);
  2. образ библиотеки: siprod.bin + объектный модуль DRAKON;
  3. запись: besmtool write <том> --from-file=<lib> --start=695;
  4. контроль: зоны читаются обратно (besmtool dump) и сличаются с образом;
  5. пуск СИПРОД (*main schema) и редактора ДРАКОН (*main drakon)
     из записанного тома (без повторной записи библиотеки).

Примеры:
    python3 tools/record2348.py                          # всё по умолчанию
    python3 tools/record2348.py --zip=disk2348.zip       # образ из архива
    python3 tools/record2348.py --source=/путь/к/2348    # готовый образ
    python3 tools/record2348.py --in-place --source=...  # писать прямо в том
    python3 tools/record2348.py --force                  # перезаписать том
    python3 tools/record2348.py --no-run                 # без пуска заданий

Без --source/--zip образ ищется в $BESM6_SHARE/2348, затем архив
disk2348.zip в текущем каталоге, каталоге репозитория и upload/.
Каталог результата: $RECORD2348_TARGET, иначе download/disk2348 рядом
с репозиторием, иначе ./disk2348.  Инструменты: besmtool, dispak
(https://github.com/Azizz8618/dispak) - в PATH; каталог share БЭСМ-6 -
в $BESM6_SHARE.
"""
import argparse
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "drakon"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

ZONE_WORDS = 1024              # зона тома: 1024 слова
ZONE_BYTES = ZONE_WORDS * 6    # слово в образе besmtool - 6 байт (без тега)
DEFAULT_ZONE = 695             # 0o1267 - PERSO СИПРОДа на томе 2348
DEFAULT_VOLUME = "2348"
ARCHIVE_NAME = "disk2348.zip"  # имя архива для автопоиска


def share():
    return os.environ.get("BESM6_SHARE", "/usr/local/share/besm6")


def need_tools(run_needed):
    """besmtool нужен всегда, dispak - только при пуске заданий."""
    names = ["besmtool"] + (["dispak"] if run_needed else [])
    missing = [n for n in names if shutil.which(n) is None]
    if missing:
        sys.exit("нет инструментов: %s\n"
                 "  добавьте каталог с ними в PATH\n"
                 "  (см. https://github.com/Azizz8618/dispak)" % ", ".join(missing))


def default_target():
    env = os.environ.get("RECORD2348_TARGET")
    if env:
        return os.path.abspath(env)
    dl = os.path.abspath(os.path.join(ROOT, "..", "download"))
    if os.path.isdir(dl):
        return os.path.join(dl, "disk2348")
    return os.path.abspath("disk2348")


def find_archive():
    """disk2348.zip: текущий каталог, репозиторий и до трёх уровней
    вверх от него, каждый раз с заходом в upload/ рядом."""
    dirs = [os.getcwd()]
    d = ROOT
    for _ in range(3):
        dirs.append(d)
        dirs.append(os.path.join(d, "upload"))
        d = os.path.dirname(d)
    for p in dirs:
        q = os.path.abspath(os.path.join(p, ARCHIVE_NAME))
        if os.path.isfile(q):
            return q
    return None


def check_image(path):
    """Число зон тома (образ кратен зоне; слово - 6 байт)."""
    size = os.path.getsize(path)
    if size == 0 or size % ZONE_BYTES:
        sys.exit("%s: размер %d байт не кратен зоне (%d байт) - "
                 "это не образ диска БЭСМ-6?" % (path, size, ZONE_BYTES))
    return size // ZONE_BYTES


def extract_from_zip(archive, out_path, volume):
    """Выложить образ тома из архива (имя файла тома внутри - любое)."""
    with zipfile.ZipFile(archive) as zf:
        members = [m for m in zf.infolist()
                   if os.path.basename(m.filename) == volume and not m.is_dir()]
        if not members:
            sys.exit("в %s нет файла %r" % (archive, volume))
        m = members[0]
        with zf.open(m) as src, open(out_path, "wb") as dst:
            shutil.copyfileobj(src, dst)
        print("   из архива: %s (%s, %d байт)" % (archive, m.filename, m.file_size))


def build_lib_with_drakon(out_path):
    """siprod.bin + объектный модуль DRAKON -> образ библиотеки.

    Объект собирается полностью: свой код, свои константы (КОНД),
    ПАМ - в bss, и проверенная таблица символов DRAKON_SYM.
    """
    from drakon.mklib import build_library, parse_data, DRAKON_SYM  # noqa: E402
    from siprod_asm import assemble_text            # noqa: E402
    from siprod_lib import Library                  # noqa: E402

    src = os.path.join(ROOT, "drakon", "drakon.be")
    cmd, _labels, _syms = assemble_text(src)
    const, data = parse_data(src)
    lib = Library(os.path.join(ROOT, "siprod.bin"))
    img = build_library(lib, "DRAKON", cmd, const=const, data=data,
                        sym=DRAKON_SYM)
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


def read_back(vol_dir, volume, start, nzones, tmp):
    """Прочитать зоны тома обратно в файл."""
    out = os.path.join(tmp, "readback.bin")
    besmtool(["dump", volume, "--start=%d" % start, "--length=%d" % nzones,
              "--to-file=%s" % out], vol_dir)
    return out


def compare_images(lib_path, readback_path, start):
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
                      % (w, start + w // 1024, want.hex(), got.hex()))
        else:
            ok += 1
    return ok, bad, len(lib) // 6


def run_job(vol_dir, volume, zone, entry, inp_lines):
    """Задание dispak из записанного тома (библиотека НЕ переписывается)."""
    work = mkdtemp()
    z = "%o" % zone
    lines = ["ШИФР 419900ЗС5^ОЗУ 32^ТРА 100^АЦП 64^ЛЕН 67(%s)^ЕЕВ1А3" % volume,
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
    ap = argparse.ArgumentParser(
        description="Запись библиотеки СИПРОД+DRAKON на том 2348")
    ap.add_argument("--source", default=None, metavar="ОБРАЗ",
                    help="исходный образ тома (иначе архив или $BESM6_SHARE)")
    ap.add_argument("--zip", default=None, metavar="АРХИВ",
                    help="архив disk2348.zip: образ берётся из него")
    ap.add_argument("--target", default=None, metavar="КАТ",
                    help="каталог для записанного тома (по умолчанию "
                         "$RECORD2348_TARGET, download/disk2348, ./disk2348)")
    ap.add_argument("--in-place", action="store_true",
                    help="писать прямо в --source, без рабочей копии")
    ap.add_argument("--force", action="store_true",
                    help="переписать том, даже если запись уже была (.recorded)")
    ap.add_argument("--zone", type=int, default=DEFAULT_ZONE, metavar="N",
                    help="начальная зона PERSO (по умолчанию %d = 0o%%o)"
                         % DEFAULT_ZONE % DEFAULT_ZONE)
    ap.add_argument("--volume", default=DEFAULT_VOLUME, metavar="ИМЯ",
                    help="имя тома (по умолчанию %s)" % DEFAULT_VOLUME)
    ap.add_argument("--lib", default=None, metavar="ОБРАЗ",
                    help="готовый образ библиотеки (иначе собирается)")
    ap.add_argument("--plain", action="store_true",
                    help="записать siprod.bin без модуля DRAKON")
    ap.add_argument("--no-run", action="store_true",
                    help="не пускать задания, только записать и сличить")
    args = ap.parse_args()

    if args.zip and args.in_place:
        sys.exit("--zip несовместим с --in-place: архив разворачивается "
                 "в рабочую копию")
    need_tools(run_needed=not args.no_run)

    # --- 1. том: рабочая копия или запись прямо в указанный образ -------
    in_place = args.in_place
    if in_place:
        if not args.source:
            sys.exit("--in-place требует --source=<образ тома>")
        src = os.path.abspath(args.source)
        if not os.path.isfile(src):
            sys.exit("нет файла %s" % src)
        vol_dir, vol = os.path.dirname(src), os.path.basename(src)
        if vol != args.volume:
            print("внимание: файл %s, имя тома %s - besmtool ищет файл "
                  "с именем тома" % (vol, args.volume))
            args.volume = vol
        vol_path = src
        total = check_image(vol_path)
        print("1) том (in-place): %s, %d зон" % (vol_path, total))
        marker = os.path.join(vol_dir, ".recorded-" + vol)
    else:
        archive = args.zip or find_archive()
        target = os.path.abspath(args.target or default_target())
        os.makedirs(target, exist_ok=True)
        vol_dir, vol = target, args.volume
        vol_path = os.path.join(vol_dir, vol)
        marker = os.path.join(vol_dir, ".recorded")

        if os.path.isfile(vol_path) and not args.force:
            print("1) том уже есть: %s (перезаписать - --force)" % vol_path)
        else:
            if archive:
                print("1) том из архива: %s -> %s" % (archive, vol_path))
                extract_from_zip(archive, vol_path, vol)
            else:
                src = args.source or os.path.join(share(), args.volume)
                if not os.path.isfile(src):
                    sys.exit("нет ни архива %s, ни образа %s - задайте "
                             "--source или --zip" % (ARCHIVE_NAME, src))
                print("1) том-источник: %s -> %s" % (src, vol_path))
                shutil.copy(src, vol_path)
            if os.path.exists(marker):
                os.remove(marker)
        total = check_image(vol_path)

    # --- 2. образ библиотеки ---------------------------------------------
    print("2) образ библиотеки")
    lib_path = args.lib or os.path.join(vol_dir, "lib.bin")
    if not args.lib:
        if args.plain:
            shutil.copy(os.path.join(ROOT, "siprod.bin"), lib_path)
        else:
            build_lib_with_drakon(lib_path)
    nzones = -(-os.path.getsize(lib_path) // ZONE_BYTES)
    print("   %s: %d слов (%d зон)"
          % (lib_path, os.path.getsize(lib_path) // 6, nzones))
    if args.zone + nzones > total:
        sys.exit("зоны %d..%d выходят за конец тома (%d зон)"
                 % (args.zone, args.zone + nzones - 1, total))

    # --- 3. запись в PERSO ------------------------------------------------
    if os.path.exists(marker) and not args.force and not in_place:
        print("3) запись уже выполнена (%s); перезаписать - --force" % marker)
    else:
        print("3) запись в PERSO тома %s, зона %d (0o%o)"
              % (args.volume, args.zone, args.zone))
        out = besmtool(["write", args.volume, "--from-file=%s" % lib_path,
                        "--start=%d" % args.zone], vol_dir)
        sys.stdout.write(out)
        with open(marker, "w") as f:
            f.write("ok\n")

    # --- 4. контроль записи ------------------------------------------------
    print("4) контроль записи")
    tmp = mkdtemp()
    rb = read_back(vol_dir, args.volume, args.zone, nzones, tmp)
    ok, bad, nwords = compare_images(lib_path, rb, args.zone)
    print("   слов сверено: %d, совпало: %d, расходится: %d"
          % (nwords, ok, bad))
    shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit("контроль записи не пройден")

    if args.no_run:
        print("\nГотово (без пуска): том %s записан" % vol_path)
        return

    # --- 5. пуск из записанного тома ---------------------------------------
    print("5) пуск из записанного тома (библиотека не переписывается)")
    probe = ["*RED", "*RG*RU", "*/*DЗАПИСЬ НА ДИСК 2348",
             "*/*DСИПРОД+ДРАКОН", "*E", "*END"]
    out = run_job(vol_dir, args.volume, args.zone, "schema", probe)
    body = printer_only(out)
    print("   *main schema: %s"
          % ("СИПРОД печатает" if "ЗАПИСЬ НА ДИСК 2348" in body
             else "ОШИБКА: выдачи нет"))
    if "ЗАПИСЬ НА ДИСК 2348" not in body:
        print(body[:800])
        sys.exit("СИПРОД из записанного тома не заработал")

    out = run_job(vol_dir, args.volume, args.zone, "drakon",
                  ["ЗАГОЛОВОК ПРОВЕРКА", "ВЕТКА ПЕРВАЯ",
                   "ДЕЙСТВИЕ ЧТО-ТО СДЕЛАТЬ", ""])
    tail = out[-400:]
    print("   *main drakon: модуль отработал и вернулся в монитор"
          if "КОНЕЦ ЗАДАЧИ" in out else "   *main drakon: НЕТ КОНЦА ЗАДАЧИ")
    if "КОНЕЦ ЗАДАЧИ" not in out:
        print(tail)
        sys.exit("модуль DRAKON не вернулся в монитор")

    print("\nГотово: том %s записан и проверен" % vol_path)
    print("Пуск СИПРОДа из него: BESM6_PATH=<каталог тома> dispak <задание>,")
    print("  в задании: ЛЕН 67(%s), *perso:67%o, *main schema" %
          (args.volume, args.zone))


if __name__ == "__main__":
    main()
