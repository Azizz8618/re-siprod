#!/usr/bin/env python3
"""Запись мини-библиотеки OVERLAY на копию тома 2348 (Этап 0а плана ОЗУ).

Переносит утилиту сборки оверлеев OVERLAY* и OVERLAY с системного тома
2048 («МС Дубна», зона 0o1457 слова 448 и 768) на копию тома 2348 в
личную библиотеку: каталог в зоне 0o2300, тела в зоне 0o2301.

Формат инфо-слова каталога (калиброван 08.11.2026 по 289 телам трёх
библиотек тома 2348, скрипт калибровка-инфослова5.py):

    A  = bits[47:36] = 0o2000 + (слово+8) + (1 если отн.зона >= 0o40)
    bits[35:30]      = (отн.зона + 0o40) & 0o77
    bits[29:12]      = длина_загрузки * 8
    bits[11:0]       = 0

(слово+8 - позиция в файловой зоне, шапка зоны = 8 слов; 0o2000 -
база личной библиотеки, у постоянной - 0o6000.)

Шапки зон: у занятых зон связки счётчик в байтах 4-7 (LE) растёт на
0x20 от зоны к зоне (0x00028d81 в 0o2150), байты 32-39 - тот же счётчик
+0x10; остальные байты шапки совпадают.  Каталог: w0/w1 - служебные
(копируются из 0o2150), записи с w2 парами (имя, инфо), терминатор -
нулевое имя, хвост - нули; все слова каталога с тегом 0x01 (как у
записанного монитором каталога 0o2150).

Запуск:
  python3 записать-overlay-2348.py --check   # только проверка и расчёт
  python3 записать-overlay-2348.py           # проверка + запись
"""
import argparse
import hashlib
import os
import shutil
import sys as _sys

_sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "..", "tools"))
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume, text_decode, encode_word

ZB = 8256
OFF = 4
TAG = b"\x01\x00"          # тег слов каталога (как у 0o2150)

SRC2048 = None   # ищется в BESM6_PATH (том 2048)
MODS = [                  # (имя, зона, слово) на 2048
    ("OVERLAY*", 0o1457, 448),
    ("OVERLAY", 0o1457, 768),
]
def _find(name):
    import os
    for d in os.environ.get("BESM6_PATH", "").split(":"):
        if d and os.path.isfile(os.path.join(d, name)):
            return os.path.join(d, name)
    raise SystemExit("том %s не найден в BESM6_PATH" % name)

CATZONE = 0o2300          # зона каталога мини-библиотеки
BODYZONE = CATZONE + 1    # зона тел
M15 = 0o77777


def info_word(relzone, word, load):
    """Инфо-слово каталога для тела в (отн.зона, слово)."""
    carry = 1 if relzone >= 0o40 else 0
    a = 0o2000 + carry + word + 8
    b = (((relzone + 0o40) & 0o77) << 6) | ((load * 8) >> 12) & 0o77
    c = (load * 8) & 0o7777
    return (a << 36) | (b << 24) | (c << 12)


def raw_word(w48, tag=TAG):
    return w48.to_bytes(6, "little") + tag


def read_module(v8, z, w):
    """Тело модуля с 2048: список 8-байтовых слов + параметры."""
    ws, _ = v8.zone_words(z)
    w0, w2 = ws[w], ws[w + 2]
    if w0 & 0o7777 != 1:
        raise SystemExit(f"0o{z:04o} w{w}: не заголовок модуля")
    cmd, cst = w2 & M15, (w2 >> 30) & 0o7777
    sym = (w0 >> 12) & 0o7777
    disk = 3 + cmd + cst + 1 + sym
    off = w + 3 + cmd + cst
    zz, ww = z + off // 1024, off % 1024
    wsh, _ = v8.zone_words(zz)
    head = text_decode(wsh[ww]).rstrip()
    # сырые слова тела (могут пересечь границу зон)
    out = []
    for i in range(w, w + disk):
        zz, ww = z + i // 1024, i % 1024
        o = (zz + OFF) * ZB + 64 + ww * 8
        out.append(v8.raw[o:o + 8])
    return dict(head=head, cmd=cmd, const=cst, sym=sym, disk=disk,
                load=cmd + cst, raw=out)


def read_raw_zone(path, zl):
    with open(path, "rb") as f:
        f.seek((zl + OFF) * ZB)
        return f.read(ZB)


def isfree(data, zl):
    off = (zl + OFF) * ZB
    h = data[off:off + 64]
    if h[0:4] == b"\0\0\0\0" and h[10:14] == b"\x80\xc7\xf1\x05":
        return True
    return data[off:off + ZB] == b"\0" * ZB


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vol", default=None,
                    help="том 2348; по умолчанию первый в BESM6_PATH")
    ap.add_argument("--source", default=None,
                    help="том 2048; по умолчанию ищется в BESM6_PATH")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    here = os.path.dirname(os.path.abspath(__file__))
    volpath = args.vol or _find("2348")
    src = args.source or _find("2048")
    data = open(volpath, "rb").read()
    print(f"том: {volpath} (md5 {hashlib.md5(data).hexdigest()[:12]})")
    v8 = Volume(src)

    # 1. Тела на 2048
    mods = []
    for nm, z, w in MODS:
        m = read_module(v8, z, w)
        if m["head"] != nm:
            raise SystemExit(f"на 2048 0o{z:04o} w{w} голова {m['head']!r}, "
                             f"ждали {nm!r}")
        print(f"источник: {nm} 0o{z:04o} w{w}: диск {m['disk']} слов, "
              f"загрузка {m['load']}")
        mods.append(m)

    # 2. Проверки на 2348
    if not isfree(data, CATZONE) or not isfree(data, BODYZONE):
        raise SystemExit(f"зоны 0o{CATZONE:04o}/0o{BODYZONE:04o} заняты")
    print(f"зоны 0o{CATZONE:04o}/0o{BODYZONE:04o} свободны")

    # связка на месте?
    v = Volume(volpath)
    ws, _ = v.zone_words(0o2150)
    names = [text_decode(ws[i]).rstrip() for i in (2, 4)]
    if names != ["DRAKON", "REDAKT"]:
        raise SystemExit(f"в каталоге 0o2150 ждали DRAKON/REDAKT, есть {names}")
    print("связка 0o2150 (DRAKON+REDAKT) на месте")

    # 3. Расчёт инфо-слов и каталога
    entries = []
    word = 0
    for m in mods:
        if word + m["disk"] > 1024:
            raise SystemExit(f"{m['head']}: не помещается в зону тел")
        entries.append((m["head"], info_word(1, word, m["load"]),
                        m["load"], word))
        word += m["disk"]
    print("инфо-слова:")
    for nm, info, load, wpos in entries:
        print(f"  {nm:10s} тело 0o{BODYZONE:04o} w{wpos:3d} "
              f"загрузка {load:4d} инфо={info:016o}")
    word = sum(m["disk"] for m in mods)

    # 4. Сборка зон
    hdr_cat = data[(CATZONE + OFF) * ZB:(CATZONE + OFF) * ZB + 64]
    hdr_body = data[(BODYZONE + OFF) * ZB:(BODYZONE + OFF) * ZB + 64]

    # образ каталога: из 0o2150 - служебные w0/w1, хвост заполняем нулями
    tpl = data[(0o2150 + OFF) * ZB + 64:(0o2150 + OFF) * ZB + 64 + 8192]
    zone = bytearray()
    zone += tpl[0:16]                       # w0/w1 как у связки
    for nm, info, _, _ in entries:
        zone += raw_word(encode_word(nm.ljust(8)[:8]))
        zone += raw_word(info)
    zone += raw_word(0)                     # имя терминатора
    zone += raw_word(0o777777777777)        # инфо терминатора = FULWORD
    zone += raw_word(0) * (1024 - 2 - 2 * len(entries) - 2)
    assert len(zone) == 8192
    # счётчик шапки: у связки 0x00028d81 в 0o2150, шаг 0x20/зону
    base = int.from_bytes(tpl[4:8], "little")
    ctr = base + 0x20 * (CATZONE - 0o2150)
    hdr = bytearray(data[(0o2150 + OFF) * ZB:(0o2150 + OFF) * ZB + 64])
    hdr[4:8] = (ctr & 0xFFFFFFFF).to_bytes(4, "little")
    hdr[36:40] = ((ctr + 0x10) & 0xFFFFFFFF).to_bytes(4, "little")

    # образ зоны тел: шапка по правилу связки, тела слово-в-слово,
    # хвост - нули (тег 0x02, как у свободной зоны)
    ctrb = base + 0x20 * (BODYZONE - 0o2150)
    hdrb = bytearray(data[(0o2152 + OFF) * ZB:(0o2152 + OFF) * ZB + 64])
    hdrb[4:8] = (ctrb & 0xFFFFFFFF).to_bytes(4, "little")
    hdrb[36:40] = ((ctrb + 0x10) & 0xFFFFFFFF).to_bytes(4, "little")
    body = bytearray()
    for m in mods:
        for b in m["raw"]:
            body += b
    tail = bytes(data[(BODYZONE + OFF) * ZB + 64 + word * 8:
                      (BODYZONE + OFF) * ZB + 64 + 8192])
    body += tail                            # хвост свободной зоны как был
    assert len(body) == 8192

    if args.check:
        print("режим --check: запись не выполнялась")
        return

    # 5. Резерв и запись
    bak = volpath + ".bak-overlay-" + time.strftime("%Y%m%d")
    if not os.path.exists(bak):
        shutil.copy2(volpath, bak)
        print(f"резерв: {bak}")
    else:
        print(f"резерв уже есть: {bak}")
    out = bytearray(data)
    o = (CATZONE + OFF) * ZB
    out[o:o + 64] = bytes(hdr)
    out[o + 64:o + ZB] = bytes(zone)
    o = (BODYZONE + OFF) * ZB
    out[o:o + 64] = bytes(hdrb)
    out[o + 64:o + ZB] = bytes(body)
    open(volpath, "wb").write(bytes(out))
    print("записано: каталог 0o%04o, тела 0o%04o" % (CATZONE, BODYZONE))

    # 6. Контроль чтением назад
    back = open(volpath, "rb").read()
    v2 = Volume(volpath)
    ws2, _ = v2.zone_words(CATZONE)
    ok = True
    for i, (nm, info, _, _) in enumerate(entries):
        n, inf = text_decode(ws2[2 + 2 * i]).rstrip(), ws2[3 + 2 * i]
        if n != nm or inf != info:
            print(f"  НЕСХОДКА записи {nm}: прочитано {n!r} {inf:016o}")
            ok = False
    for m, (_, _, _, word) in zip(mods, entries):
        o = (BODYZONE + OFF) * ZB + 64 + word * 8
        if back[o:o + 8 * m["disk"]] != b"".join(m["raw"]):
            print(f"  НЕСХОДКА тела {m['head']}")
            ok = False
    print("контроль: записи совпадают с расчётом" if ok
          else "контроль: ЕСТЬ РАСХОЖДЕНИЯ")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
