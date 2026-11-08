#!/usr/bin/env python3
"""Калибровка инфо-слова ДМС, часть 4: полная проверка формулы + шапки.

Формула (личная библиотека):
  A = bits[47:36] = 0o2000 + (слово+8) + (1 если отн.зона >= 0o40)
  bits[35:30]     = (отн.зона + 0o40) & 0o77
  bits[29:12]     = длина_загрузки * 8
  bits[11:0]      = 0
Постоянная библиотека: база 0o6000 вместо 0o2000.
Проверяем на всех точках; печатаем шапки зон и каталогов для записи.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "tools"))
from vol import Volume, text_decode

M15 = 0o77777
LETTERS = set(" ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789*/-.+()ЦДФГИЙЛЯЖЬПЫЗШЭЩЧЮБ")


def plausible(s):
    return bool(s) and all(c in LETTERS for c in s) and s.strip() != ""


def bits(w, hi, lo):
    return (w >> lo) & ((1 << (hi - lo + 1)) - 1)


def all_bodies(v, zlo, zhi):
    out = []
    for z in range(zlo, zhi + 1):
        ws, _ = v.zone_words(z)
        for i in range(1022):
            w0 = ws[i]
            if w0 & 0o7777 != 1:
                continue
            w2 = ws[i + 2] if i + 2 < 1024 else 0
            cmd, cst = w2 & M15, (w2 >> 30) & 0o7777
            if cmd + cst > 40000 or cmd + cst == 0:
                continue
            off = i + 3 + cmd + cst
            zz, ww = z + off // 1024, off % 1024
            if zz > zhi + 1:
                continue
            wsh, _ = v.zone_words(zz)
            name = text_decode(wsh[ww]).rstrip()
            if not plausible(name):
                continue
            out.append(dict(name=name, zone=z, word=i, cmd=cmd, const=cst,
                            sym=(w0 >> 12) & 0o7777, load=cmd + cst))
    return out


def read_cat(v, cz):
    cat = []
    for zz in (cz, cz + 1):
        ws, _ = v.zone_words(zz)
        broke = False
        for i in range(2, 1022, 2):
            if ws[i] == 0:
                broke = True
                break
            cat.append((text_decode(ws[i]).rstrip(), ws[i + 1]))
        if broke:
            break
    return cat


def _find(name):
    import os
    for d in os.environ.get("BESM6_PATH", "").split(":"):
        if d and os.path.isfile(os.path.join(d, name)):
            return os.path.join(d, name)
    raise SystemExit("том %s не найден в BESM6_PATH" % name)

v = Volume(_find("2348"))
pts = []
for label, cz, zend, base in (("пост", 0o0200, 0o0250, 0o6000),
                              ("связка", 0o2150, 0o2200, 0o2000),
                              ("паскаль", 0o2570, 0o2700, 0o2000)):
    bodies = all_bodies(v, cz + 2, zend)
    cat = read_cat(v, cz)
    used = set()
    for nm, info in cat:
        L = (bits(info, 29, 24) * 4096 + bits(info, 23, 12)) / 8
        cand = [b for b in bodies if b["name"] == nm and b["load"] == L
                and (b["zone"], b["word"]) not in used]
        if len(cand) == 1:
            b = cand[0]
            used.add((b["zone"], b["word"]))
            pts.append((label, base, nm, info, b["zone"] - cz, b["word"]))

ok = fail = 0
for label, base, nm, info, relzone, word in pts:
    carry = 1 if relzone >= 0o40 else 0
    pred = ((base + carry + word + 8) << 36) \
        | (((relzone + 0o40) & 0o77) << 30) \
        | 0  # длина не проверяем здесь - она задана подбором
    # сравниваем только A и B-старшие (длина - по построению)
    a_ok = bits(info, 47, 36) == base + carry + word + 8
    b_ok = bits(info, 35, 30) == (relzone + 0o40) & 0o77
    if a_ok and b_ok:
        ok += 1
    else:
        fail += 1
        if fail <= 10:
            print(f"  НЕСХОДКА {label} {nm}: инфо={info:016o} "
                  f"A ждали {base+carry+word+8:04o} "
                  f"есть {bits(info,47,36):04o}; "
                  f"B-зона ждали {(relzone+0o40)&0o77:02o} "
                  f"есть {bits(info,35,30):02o}")
print(f"проверка A и зоны: сходится {ok}, не сходится {fail} (из {len(pts)})")

print()
print("=== шапки каталогов (слова 0-7) ===")
for cz in (0o0200, 0o2150, 0o2570):
    ws, cv = v.zone_words(cz)
    print(f"каталог 0o{cz:04o}:")
    for i in range(8):
        print(f"  w{i:2d} {'Д' if cv[i] else 'K'} {text_decode(ws[i])!r:12s} "
              f"{ws[i]:016o}")
    # и хвост: последние непустые слова
    tail = max(i for i in range(2, 1024, 2) if ws[i] != 0) + 2
    print(f"  конец списка: w{tail}")
    for i in range(tail, min(tail + 4, 1024)):
        print(f"  w{i:2d} {'Д' if cv[i] else 'K'} {text_decode(ws[i])!r:12s} "
              f"{ws[i]:016o}")

print()
print("=== шапки зон (64 байта) связки и свободной зоны ===")
raw = v.raw
ZB = 8256
for zl in (0o2150, 0o2152, 0o2165, 0o2200, 0o2201):
    off = (zl + 4) * ZB
    h = raw[off:off + 64]
    print(f"зона 0o{zl:04o}: {h[:16].hex()} | {h[16:32].hex()} | "
          f"{h[32:48].hex()} | {h[48:64].hex()}")
