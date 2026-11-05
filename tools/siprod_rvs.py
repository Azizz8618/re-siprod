#!/usr/bin/env python3
"""Связывание модулей СИПРОДа линковщиком РВС.

Модули компилируются штатным транслятором МАКРО-БЕМШ (tools/siprod_bemsh.py)
в зоны ПЕРСО тома, затем линковщик РВС («редактор внешних связей» Мониторной
системы) читает их оттуда и связывает в программу.

Задание РВС (как в re-dispak/rvs.pl):

    мдл   <имя>43<зона>^наз <адрес>^

Имя модуля в директиве - ровно 6 знаков (имя дополняется пробелами), зона
указывается восьмерично: 43 - номер ленты ПЕРСО, далее - зона тома.

Использование:
    tools/siprod_rvs.py                       # все модули
    tools/siprod_rvs.py ADRSEK RSYMB          # только эти
    tools/siprod_rvs.py --dump ADRSEK         # заголовок объектного модуля
    tools/siprod_rvs.py --zones               # только собрать объекты
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
from siprod_lib import Library, TEXT                           # noqa: E402
from siprod_dis import sanitize, symbol_table                 # noqa: E402
import siprod_bemsh as sb                                      # noqa: E402

# том с ПЕРСО (рабочая копия) и том с линковщиком РВС
VOL = os.environ.get("SIPROD_RVS_VOL", "2222")
RVS_VOL = os.environ.get("SIPROD_RVS_RVSVOL", "2113")
TAPE = "43"
# том, на котором живут транслятор и макросы
TRANS_VOL = "2048"
MACRO_VOL = "2099"


def prepare(work):
    """Рабочий каталог с копиями томов."""
    os.makedirs(work, exist_ok=True)
    for v in (TRANS_VOL, MACRO_VOL, VOL, RVS_VOL):
        dst = os.path.join(work, v)
        if not os.path.exists(dst):
            if v == VOL:
                open(dst, "wb").close()        # пустой том ПЕРСО
            else:
                shutil.copy(os.environ.get("BESM6_SHARE", "/usr/local/share/besm6") + "/%s" % v, dst)
    return dict(os.environ, BESM6_PATH=work + ":/usr/local/share/besm6")


def compile_module(lib, name, zone, work, env, textdir):
    """Скомпилировать модуль в зону ПЕРСО; вернуть (ошибки, число зон)."""
    src = sb.convert(lib, name, os.path.join(textdir,
                                             name.replace("*", "#") + ".be"))
    return compile_source(src, name, zone, work, env)


def compile_source(src, name, zone, work, env):
    """Скомпилировать исходник в зону ПЕРСО.

    Возвращает (ошибки, число зон): объектный модуль может занимать
    несколько зон (о том сообщает транслятор: «ЗАПИСАН В ЗОНЫ С ... ПО
    ...»), и следующий модуль надо класть за ними.
    """
    job = sb.make_job(src, zone=zone, vol=VOL)
    b6 = os.path.join(work, "comp_%s.b6" % name.replace("*", "#"))
    open(b6, "w", encoding="utf-8").write(job)
    r = subprocess.run(["dispak", b6], cwd=work, capture_output=True, text=True,
                       env=env)
    out = r.stdout + r.stderr
    errs = [l.strip() for l in out.splitlines() if l.strip().startswith("ОШ ")]
    m = re.search(r"ЧИСЛО ОШИБОК=(\d+)", out)
    if m and int(m.group(1)):
        errs.append("ошибок транслятора: %s" % m.group(1))
    nzones = 1
    m = re.search(r"ЗОНЫ С \S+ ПО (\S+)", out)
    if m:
        nzones = int(m.group(1).split()[-1], 8) - int(zone, 8) + 1
    return errs, nzones


def common_blocks(lib):
    """Общие блоки библиотеки: имя -> размер в словах.

    В таблице символов модуля общий блок записан записью вида
    ('lc', '*ИМЯ*', размер).  В исходной библиотеке (формат DMS) общие
    блоки отдельных объектов не имеют, но для связывания достаточно
    объявить их модулями с одними данными.
    """
    out = {}
    for name in lib.objects:
        _ext, _labels, symtab = symbol_table(lib, name)
        for e in symtab:
            if e and e[0] == "lc":
                blk = e[1].strip("*")
                size = e[2]
                if blk and size and blk not in out:
                    out[blk] = size
    return out


def block_source(name, size):
    """Исходник модуля-общего блока: одна переменная в size слов."""
    return "%s\tСТАРТ %d\n\tЕ\n\tМ\nV0\tПАМ\t%d\n\tФИНИШ\n" % (name, sb.LOAD,
                                                                size)


def object_name(work, vol, zone):
    """Имя модуля из заголовка объектного модуля (слово 1).

    Имя занимает шесть байт, по одному на знак: код знака в кодировке
    TEXT мониторной системы, к нему добавлен признак 0x80.
    """
    out = os.path.join(work, "zone.bin")
    r = subprocess.run(["besmtool", "dump", vol, "--start=%d" % zone,
                        "--length=1", "--to-file=" + out], cwd=work,
                       env=dict(os.environ, BESM6_PATH=work + ":/usr/local/share/besm6"),
                       capture_output=True)
    if r.returncode or not os.path.exists(out):
        return None
    data = open(out, "rb").read()
    if len(data) < 12:
        return None
    inv = dict((i, c) for i, c in enumerate(TEXT))
    return "".join(inv.get(b & 0o77, "?") for b in data[6:12]).rstrip()


def link(mods, work, env, outzone):
    """mods: список (имя, зона ПЕРСО, адрес загрузки, число зон, начало блока).

    Имя в директиве `мдл` - ровно шесть знаков, как в объектном модуле:
    не хватает - пробелами.  Модули собираются в блоки - группы, которые
    РВС размещает подряд, начиная с адреса, заданного директивой `наз`
    (у первого модуля блока); у блока - своя зона для связанной программы
    (`зонгп`), иначе РВС пишет «ПОВТОРНАЯ ЗАПИСЬ».
    """
    lines = []
    z = int(outzone, 8)
    for name, zone, addr, nzones, first in mods:
        sname = (sanitize(name) or name)[:6]
        if first:
            lines.append("мдл   %-6s%s%s^наз   %05o^зонгп 43%04o %6o^"
                         % (sname, TAPE, zone, addr, z, nzones))
            z += nzones
        else:
            lines.append("мдл   %-6s%s%s^" % (sname, TAPE, zone))
    job = """шифр 419999^
лен 67(2248)42(%s)^
лен 43(%s-зп)^
росп 0^
вход 1000^
е
в 1000
к 00 070 1003
к 00 070 1004
к 00 30 70000
с 0010 3400 0067 0105
с 0010 3500 0067 0106
в 2000
а1
%sконец ^
_$
еконец
""" % (RVS_VOL, VOL, "\n".join(lines) + "\n")
    b6 = os.path.join(work, "link.b6")
    open(b6, "w", encoding="utf-8").write(job)
    r = subprocess.run(["dispak", b6], cwd=work, capture_output=True, text=True,
                       env=env)
    return r.stdout + r.stderr


def save_mods(work, mods):
    """Сохранить список модулей (для повторного связывания)."""
    path = os.path.join(work, "mods.txt")
    with open(path, "w", encoding="utf-8") as f:
        for m in mods:
            f.write("%s\t%s\t%o\t%d\t%d\n" % (m[0], m[1], m[2], m[3], m[4]))
    return path


def load_mods(work):
    """Прочитать список модулей, сохранённый save_mods()."""
    path = os.path.join(work, "mods.txt")
    mods = []
    for line in open(path, encoding="utf-8"):
        nm, z, addr, nz, first = line.rstrip("\n").split("\t")
        mods.append([nm, z, int(addr, 8), int(nz), int(first)])
    return mods


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("modules", nargs="*", help="модули (по умолчанию - все)")
    ap.add_argument("--work", default="/tmp/siprod-rvs",
                    help="рабочий каталог с копиями томов")
    ap.add_argument("--text", default=os.path.join(ROOT, "bemsh"))
    ap.add_argument("--image", default=os.path.join(ROOT, "siprod.bin"))
    ap.add_argument("--first-zone", default="0100",
                    help="первая зона ПЕРСО для объектных модулей")
    ap.add_argument("--base", default="01000",
                    help="начальный адрес загрузки для РВС (5 знаков октально)")
    ap.add_argument("--out-zone", default="0700",
                    help="зона ПЕРСО для связанной программы")
    ap.add_argument("--block", type=int, default=1024,
                    help="размер блока модулей в словах (зона - 1024)")
    ap.add_argument("--dump", action="store_true",
                    help="показать имя модуля в объектном модуле")
    ap.add_argument("--zones", action="store_true",
                    help="только собрать объектные модули, не связывать")
    ap.add_argument("--no-blocks", dest="blocks", action="store_false",
                    help="не собирать общие блоки")
    ap.add_argument("--out", default=None,
                    help="куда записать полный вывод РВС")
    args = ap.parse_args()

    env = prepare(args.work)
    lib = Library(args.image)
    names = args.modules or sorted(lib.objects)
    zone = int(args.first_zone, 8)
    base = int(args.base, 8)
    mods, bad = [], []
    addr = base
    block_len = 0
    block_no = 0
    block_first = None
    i = 0
    for name in names:
        z = "%04o" % zone
        errs, nzones = compile_module(lib, name, z, args.work, env, args.text)
        if errs:
            bad.append((name, errs))
        zone += nzones            # объектный модуль занимает nzones зон
        # длина модуля при загрузке - из исходной библиотеки
        s, h = lib.objects[name]
        length = h["cmd"] + h["const"] + h["bss"]
        # блок - группа модулей, занимающая примерно зону (1024 слова);
        # модули блока РВС размещает подряд, начиная с адреса блока
        first = block_len == 0
        if first:
            block_no += 1
            block_first = len(mods)
        mods.append([name, z, addr, 0, first])
        addr += length + 8
        block_len += length + 8
        if block_len >= args.block:
            # блок заполнен: под него отводим зону программы и ещё одну -
            # под оглавление символов
            mods[block_first][3] = (block_len + 1023) // 1024 + 1
            block_len = 0
    if block_len:
        mods[block_first][3] = (block_len + 1023) // 1024 + 1
    # общие блоки - модули с одними данными: без них ссылки на блоки
    # не разрешаются и связывание обрывается
    blocks = common_blocks(lib)
    if args.blocks:
        for blk, size in sorted(blocks.items()):
            z = "%04o" % zone
            errs, nzones = compile_source(block_source(blk, size), blk, z,
                                          args.work, env)
            zone += nzones
            if errs:
                bad.append((blk, errs))
            mods.append([blk, z, addr, 1, True])
            addr += size + 8
    print("собрано модулей: %d, с ошибками: %d, блоков: %d, общих блоков: %d, "
          "зон ПЕРСО: %d" % (len(mods), len(bad), block_no,
                             len(blocks) if args.blocks else 0, zone))
    for name, errs in bad:
        print("   %-10s %s" % (name, errs[:2]))
    if args.dump:
        for m in mods:
            print("   %-10s зона %s  имя в объекте: %r"
                  % (m[0], m[1], object_name(args.work, VOL, int(m[1], 8))))
    if args.zones:
        save_mods(args.work, mods)
        return 1 if bad else 0
    print("---- РВС ----")
    save_mods(args.work, mods)
    out = link(mods, args.work, env, args.out_zone)
    if args.out:
        open(args.out, "w", encoding="utf-8").write(out)
    lines = out.splitlines()
    print("\n".join(lines[:6]))
    net = [l.strip() for l in lines if "НЕТ МДЛ" in l]
    zg = [l.strip() for l in lines if "ЗОНГП" in l]
    print("...")
    print("неразрешённых ссылок: %d, связано программ: %d"
          % (len(net), len(zg)))
    missing = {}
    for l in net:
        m = re.search(r"НЕТ МДЛ\s+(\S+)", l)
        if m:
            missing[m.group(1)] = missing.get(m.group(1), 0) + 1
    for nm, cnt in sorted(missing.items()):
        print("   не найден: %-10s (%d)" % (nm, cnt))
    for l in zg[:5]:
        print("   ", l)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
