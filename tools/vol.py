#!/usr/bin/env python3
"""Читатель томов БЭСМ-6 формата dispak (disk_readi2, zone_t).

Файл: зоны по 8256 байт: 8 контрольных слов uint64 + 1024 слова uint64
(little-endian; младшие 6 байт = 48-битное слово, бит 48 = свёртка
0=команда/1=данные).  Логическая зона L лежит в файловой зоне L+4
(ZONE_OFFSET).  Имена - код TEXT (см. re-siprod/tools/siprod_lib.py).
"""
import sys

TEXT = [" ", ".", "Б", "Ц", "Д", "Ф", "Г", "И", "(", ")", "*", "Й",
        "Л", "Я", "Ж", "/", "0", "1", "2", "3", "4", "5", "6", "7",
        "8", "9", "Ь", ",", "П", "-", "+", "Ы", "З", "A", "B", "C",
        "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O",
        "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "Ш",
        "Э", "Щ", "Ч", "Ю"]
ZW = 1024
ZBYTES = 8256
OFF = 4                      # файловая зона = логическая + 4
M48 = (1 << 48) - 1


def text_decode(w):
    return "".join(TEXT[(w >> (42 - 6 * i)) & 0x3F] for i in range(8))


def encode_word(s):
    v = 0
    for ch in s.ljust(8)[:8]:
        v = (v << 6) | TEXT.index(ch)
    return v


class Volume:
    def __init__(self, path):
        self.path = path
        data = open(path, "rb").read()
        self.raw = data
        self.nzones = len(data) // ZBYTES
        self.nwords = self.nzones * ZW
        self.words = []
        self.conv = []
        for z in range(self.nzones):
            off = z * ZBYTES + 64
            chunk = data[off:off + 8192]
            us = [int.from_bytes(chunk[i*8:i*8+8], "little") for i in range(ZW)]
            self.words += [u & M48 for u in us]
            self.conv += [1 - ((u >> 48) & 1) for u in us]   # 1=данные

    def zone_words(self, zlog):
        """Слова логической зоны zlog (список int) и свёртки."""
        b = (zlog + OFF) * ZW
        return self.words[b:b + ZW], self.conv[b:b + ZW]

    def word(self, zlog, i):
        return self.words[(zlog + OFF) * ZW + i]

    def dump(self, zlog, start=0, count=32, out=sys.stdout):
        ws, cv = self.zone_words(zlog)
        print(f"=== зона {zlog} = 0o{zlog:04o} ({self.path})", file=out)
        for i in range(start, min(ZW, start + count)):
            print(f"w{i:4d} {'Д' if cv[i] else 'K'} {text_decode(ws[i])!r:12s}"
                  f" {ws[i]:012o}", file=out)
