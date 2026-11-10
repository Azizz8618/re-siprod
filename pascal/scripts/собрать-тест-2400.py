#!/usr/bin/env python3
"""Чистая сборка тестовой библиотеки на копии тома (без инкрементных правок).

Всё с нуля от эталона work/twophase/2348:
  - связка 0o2150..0o2173 -> 0o2400..0o2423 (шапки: счётчик +0x20/зону);
  - тело LIBDELET (0o0231 w160, 84 слова) -> 0o2424 w0,
    шапка 0o2424 = шапка 0o2423 + 0x20;
  - в каталог 0o2400 перед терминатором вставляется запись OVERLAYT
    (копия записи REDAKT, тело 0o2402 w0 - настоящее) - проверка сдвига;
  - контрольная запись LIBDELET НЕ добавляется (чистый тест сдвига).
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vol import Volume, text_decode, encode_word

ZB = 8256
OFF = 4
def _find(name):
    import os
    paths = [os.path.join(d, name)
             for d in os.environ.get("BESM6_PATH", "").split(":")
             if d and os.path.isfile(os.path.join(d, name))]
    if not paths:
        raise SystemExit("том %s не найден в BESM6_PATH" % name)
    return paths

_paths = _find("2348")
VOL = _paths[0]          # рабочая копия - первый в BESM6_PATH
REF = _paths[1] if len(_paths) > 1 else VOL   # эталон - второй

ref = open(REF, "rb").read()
data = bytearray(open(VOL, "rb").read())

# 1. Связка -> 0o2400
for i in range(0o24):
    so, do = (0o2150 + i + OFF) * ZB, (0o2400 + i + OFF) * ZB
    blk = bytearray(ref[so:so + ZB])
    base = int.from_bytes(blk[4:8], "little")
    ctr = base + 0x20 * (0o2400 + i - 0o2150)
    blk[4:8] = (ctr & 0xFFFFFFFF).to_bytes(4, "little")
    blk[36:40] = ((ctr + 0x10) & 0xFFFFFFFF).to_bytes(4, "little")
    data[do:do + ZB] = bytes(blk)
print("связка 0o24 зоны -> 0o2400")

# 2. Каталог 0o2400: вставить OVERLAYT (= запись REDAKT) перед терминатором
zc = (0o2400 + OFF) * ZB + 64
old = bytes(data[zc:zc + 8192])
nm_red, inf_red = old[4 * 8:5 * 8], old[5 * 8:6 * 8]   # запись REDAKT
entry = encode_word("OVERLAYT").to_bytes(6, "little") + bytes([0, 0]) + inf_red
new = old[:6 * 8] + entry + old[6 * 8:24 * 8] + old[26 * 8:]
assert len(new) == 8192, len(new)
data[zc:zc + 8192] = new
print("запись OVERLAYT (= REDAKT, тело 0o2402 w0) вставлена на w6/7")

# 3. Контроль структуры каталога (в памяти)
def words48(buf, base, n):
    return [int.from_bytes(buf[base + i * 8:base + i * 8 + 6], "little")
            for i in range(n)]

wsx = words48(data, zc, 14)
assert text_decode(wsx[2]).rstrip() == "DRAKON"
assert text_decode(wsx[4]).rstrip() == "REDAKT"
assert text_decode(wsx[6]).rstrip() == "OVERLAYT"
assert wsx[8] == 0 and wsx[9] == 0o7777777777777777, (wsx[8], wsx[9])
assert text_decode(wsx[10]).rstrip() != ""     # баннер на w10-13
print("каталог: DRAKON, REDAKT, OVERLAYT, терминатор w8/9, баннер w10-13 - ОК")

open(VOL, "wb").write(bytes(data))
print("записано")

# 3. Контроль структуры каталога (перечитываем файл)
v = Volume(VOL)
ws, _ = v.zone_words(0o2400)
assert text_decode(ws[2]).rstrip() == "DRAKON", text_decode(ws[2])
assert text_decode(ws[4]).rstrip() == "REDAKT"
assert text_decode(ws[6]).rstrip() == "OVERLAYT"
assert ws[8] == 0 and ws[9] == 0o7777777777777777, (ws[8], ws[9])
assert text_decode(ws[10]).rstrip() != ""     # баннер на w10-13
print("контроль перечитыванием: ОК")

# 4. Контроль: вне копии том не изменился
for fz in range(4, len(ref) // ZB):
    if 0o2404 <= fz < 0o2404 + 0o24:      # файловые зоны копии
        continue
    if ref[fz * ZB:(fz + 1) * ZB] != bytes(data[fz * ZB:(fz + 1) * ZB]):
        raise SystemExit(f"КРИТИЧНО: зона {fz} изменилась вне копии")
print("вне 0o2400-0o2423 том не тронут: ОК")

open(VOL, "wb").write(bytes(data))
print("записано")
