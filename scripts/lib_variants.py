#!/usr/bin/env python3
"""Варианты библиотеки СИПРОД+DRAKON для бисекции отказа загрузчика.

Каждый вариант - функция, строящая список слов библиотеки из исходного
siprod.bin и слов объекта DRAKON.  Запуск: python3 scripts/lib_variants.py
пишет scripts/out/variant-<имя>.bin и печатает сводку.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from siprod_lib import Library, text_encode, text_decode   # noqa: E402

SIPROD = os.path.join(ROOT, "siprod.bin")
OBJWORDS = os.path.join(HERE, "out", "drakon_obj_words.txt")


def base_words():
    lib = Library(SIPROD)
    return list(lib.words), lib


def catalog_n(words):
    n = 1
    while True:
        nm = text_decode(words[2 * n]).rstrip()
        if not nm or not all(c.isalnum() or c in "/*" for c in nm):
            break
        n += 1
    return n


def add_entry(words, n, rec, after_term=False):
    """Запись DRAKON: на месте завершателя (after_term=False) или за ним."""
    if after_term:
        words[2 * n] = 0
        words[2 * n + 1] = 0o7777777777777777
        words[2 * n + 2] = text_encode("DRAKON")
        words[2 * n + 3] = rec
        words[2 * n + 4] = 0
        words[2 * n + 5] = 0o7777777777777777
    else:
        words[2 * n] = text_encode("DRAKON")
        words[2 * n + 1] = rec
        words[2 * n + 2] = 0
        words[2 * n + 3] = 0o7777777777777777
    return words


def put_image(words, obj, pos):
    if len(words) < pos + len(obj):
        words.extend([0] * (pos + len(obj) - len(words)))
    words[pos:pos + len(obj)] = obj
    return words


def v_baseline(words, lib, obj):
    """Текущая сборка: запись на месте завершателя, образ за STANDA."""
    n = catalog_n(words)
    end = 0
    for nm, (s, h) in lib.objects.items():
        total = 3 + h["cmd"] + h["const"] + h["data"] + h["set_"] \
            + h["head"] + h["sym"] + h["long"] + h["debug"]
        end = max(end, s + total)
    pos = lib.nwords          # за всеми разделами библиотеки (комментарии)
    date22 = max(words[2 * i + 1] >> 26 for i in range(1, n)
                 if text_decode(words[2 * i]).rstrip())
    rec = (date22 << 26) | ((370 * 8) << 12)
    add_entry(words, n, rec)
    put_image(words, obj, pos)
    return words


def v_after_term(words, lib, obj):
    """Запись ЗА завершателем (loader.md п.4 буквально)."""
    n = catalog_n(words)
    end = 0
    for nm, (s, h) in lib.objects.items():
        total = 3 + h["cmd"] + h["const"] + h["data"] + h["set_"] \
            + h["head"] + h["sym"] + h["long"] + h["debug"]
        end = max(end, s + total)
    pos = lib.nwords          # за всеми разделами библиотеки (комментарии)
    date22 = max(words[2 * i + 1] >> 26 for i in range(1, n)
                 if text_decode(words[2 * i]).rstrip())
    rec = (date22 << 26) | ((370 * 8) << 12)
    add_entry(words, n, rec, after_term=True)
    put_image(words, obj, pos)
    return words


def v_zero_date(words, lib, obj):
    n = catalog_n(words)
    end = 0
    for nm, (s, h) in lib.objects.items():
        total = 3 + h["cmd"] + h["const"] + h["data"] + h["set_"] \
            + h["head"] + h["sym"] + h["long"] + h["debug"]
        end = max(end, s + total)
    pos = (end + 31) // 32 * 32
    rec = (370 * 8) << 12
    add_entry(words, n, rec)
    put_image(words, obj, pos)
    return words


def v_image_first(words, lib, obj):
    """Образ в свободной зоне ПЕРЕД модулями (без сдвига, 32-выравнено)."""
    n = catalog_n(words)
    date22 = max(words[2 * i + 1] >> 26 for i in range(1, n)
                 if text_decode(words[2 * i]).rstrip())
    rec = (date22 << 26) | ((370 * 8) << 12)
    add_entry(words, n, rec)
    start = (5120 - len(obj)) // 32 * 32
    put_image(words, obj, start)
    return words


def v_no_image(words, lib, obj):
    """Запись каталога есть, образа нет (проверка каталог-only)."""
    n = catalog_n(words)
    date22 = max(words[2 * i + 1] >> 26 for i in range(1, n)
                 if text_decode(words[2 * i]).rstrip())
    rec = (date22 << 26) | ((370 * 8) << 12)
    add_entry(words, n, rec)
    return words


def v_no_entry(words, lib, obj):
    """Образ есть (в конце), записи каталога нет."""
    put_image(words, obj, lib.nwords)
    return words


def v_standa_rec(words, lib, obj):
    """Запись = копия записи STANDA (дата/длина как у рабочего модуля)."""
    n = catalog_n(words)
    lib2 = Library(SIPROD)
    rec = lib2.catalog["STANDA"]
    add_entry(words, n, rec)
    put_image(words, obj, lib.nwords)
    return words


def v_standa_date(words, lib, obj):
    """Дата из записи STANDA, длина - своя (370 слов)."""
    n = catalog_n(words)
    lib2 = Library(SIPROD)
    rec_s = lib2.catalog["STANDA"]
    date22 = rec_s >> 26
    rec = (date22 << 26) | ((370 * 8) << 12)
    add_entry(words, n, rec)
    put_image(words, obj, lib.nwords)
    return words


def v_standa_date_contig(words, lib, obj):
    """Дата STANDA, своя длина, образ вплотную за STANDA (21600)."""
    n = catalog_n(words)
    lib2 = Library(SIPROD)
    rec_s = lib2.catalog["STANDA"]
    date22 = rec_s >> 26
    rec = (date22 << 26) | ((370 * 8) << 12)
    add_entry(words, n, rec)
    put_image(words, obj, 21600)
    return words


def _len8_variant(words, lib, obj, nwords):
    n = catalog_n(words)
    lib2 = Library(SIPROD)
    rec_s = lib2.catalog["STANDA"]
    date22 = rec_s >> 26
    rec = (date22 << 26) | ((nwords * 8) << 12)
    add_entry(words, n, rec)
    put_image(words, obj, lib.nwords)
    return words


def v_len180(words, lib, obj):
    return _len8_variant(words, lib, obj, 180)


def v_len360(words, lib, obj):
    return _len8_variant(words, lib, obj, 360)


def v_len369(words, lib, obj):
    return _len8_variant(words, lib, obj, 369)


def v_len370(words, lib, obj):
    return _len8_variant(words, lib, obj, 370)


def v_len371(words, lib, obj):
    return _len8_variant(words, lib, obj, 371)


def v_len436(words, lib, obj):
    return _len8_variant(words, lib, obj, 436)


def v_inside24(words, lib, obj):
    """Дата STANDA, длина 370, образ СЛОВО 24000 (внутри 24 зон)."""
    n = catalog_n(words)
    lib2 = Library(SIPROD)
    date22 = lib2.catalog["STANDA"] >> 26
    rec = (date22 << 26) | ((370 * 8) << 12)
    add_entry(words, n, rec)
    put_image(words, obj, 24000)
    return words


def v_before_wrzona(words, lib, obj):
    """DRAKON ПЕРЕД WRZONA (запись 0o20 - служебный маркер?)."""
    n = catalog_n(words)          # завершатель на словах 2n,2n+1
    lib2 = Library(SIPROD)
    date22 = lib2.catalog["STANDA"] >> 26
    rec = (date22 << 26) | ((370 * 8) << 12)
    # n = 109: WRZONA = запись 108 на словах 216,217; завершатель 218,219
    words[216] = text_encode("DRAKON")
    words[217] = rec
    words[218] = text_encode("WRZONA")
    words[219] = 0o20
    words[220] = 0
    words[221] = 0o7777777777777777
    put_image(words, obj, lib.nwords)
    return words


VARIANTS = {
    "baseline": v_baseline,
    "after-term": v_after_term,
    "zero-date": v_zero_date,
    "image-first": v_image_first,
    "no-image": v_no_image,
    "no-entry": v_no_entry,
    "standa-rec": v_standa_rec,
    "standa-date": v_standa_date,
    "standa-date-contig": v_standa_date_contig,
    "len180": v_len180,
    "len360": v_len360,
    "len369": v_len369,
    "len370": v_len370,
    "len371": v_len371,
    "len436": v_len436,
    "inside24": v_inside24,
    "before-wrzona": v_before_wrzona,
}


def main():
    obj = [int(l, 8) for l in open(OBJWORDS)]
    only = sys.argv[1:] or list(VARIANTS)
    outdir = os.path.join(HERE, "out")
    os.makedirs(outdir, exist_ok=True)
    for name in only:
        words, lib = base_words()
        words = VARIANTS[name](words, lib, obj)
        out = os.path.join(outdir, "variant-%s.bin" % name)
        with open(out, "wb") as f:
            for w in words:
                f.write((w & 0xffffffffffff).to_bytes(6, "big"))
        print("%-12s -> %s (%d зон)" % (name, out, -(-len(words) // 1024)))


if __name__ == "__main__":
    main()
