#!/usr/bin/env python3
"""Чтение личной библиотеки СИПРОДа (PERSO, зона 2702 тома 2248).

Файл `siprod.bin` - образ библиотеки в формате Мониторной системы Дубны:
две первые зоны занимает каталог, дальше идут объектные модули.

Разбор объектного модуля (формат DMS, распакованный заголовок):

    слово S+0: head_len (биты 0-11), sym_len (12-23), debug_len (36-47)
    слово S+1: set_len (0-14), data_len (15-29), long_len (30-44)
    слово S+2: cmd_len (0-14), bss_len (15-29), const_len (30-44)

    разделы: cmd [S+3 ..) | const | data | set | head | sym | long | debug | comment

`cmd` - команды (код БЕМШ), `const` - константы, `head` - имя модуля
(кодировка TEXT), `sym` - таблица символов, `long` - длинные имена,
`debug` - имена меток, `comment` - исходный текст.

Использование:
    tools/siprod_lib.py            # сводка по модулям
    tools/siprod_lib.py --dump MOD # разбор одного модуля
"""

import sys

TEXT = [" ", ".", "Б", "Ц", "Д", "Ф", "Г", "И", "(", ")", "*", "Й",
        "Л", "Я", "Ж", "/", "0", "1", "2", "3", "4", "5", "6", "7",
        "8", "9", "Ь", ",", "П", "-", "+", "Ы", "З", "A", "B", "C",
        "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O",
        "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "Ш",
        "Э", "Щ", "Ч", "Ю"]

M15 = 0o77777
M12 = 0o7777


def text_decode(word):
    """Слово -> 8 символов кодировки TEXT."""
    return "".join(TEXT[(word >> (42 - 6 * i)) & 0x3F] for i in range(8))


def text_encode(name):
    """Строка -> слово кодировки TEXT (8 символов, дополненных пробелами)."""
    v = 0
    for ch in name.ljust(8)[:8]:
        v = (v << 6) | TEXT.index(ch)
    return v


class Library:
    """Образ личной библиотеки: слова, каталог и объектные модули."""

    def __init__(self, path):
        with open(path, "rb") as f:
            data = f.read()
        self.data = data
        self.nwords = len(data) // 6
        self.words = [int.from_bytes(data[i * 6:i * 6 + 6], "big")
                      for i in range(self.nwords)]
        self.catalog = self._read_catalog()
        self.objects = self._find_objects()

    # --- каталог -----------------------------------------------------------
    def _read_catalog(self):
        """Каталог модулей: имя -> запись (слово)."""
        cat = {}
        i = 2
        while i + 1 < self.nwords:
            name = text_decode(self.words[i]).rstrip()
            if not name or not all(c.isalnum() or c in "/*" for c in name):
                break
            cat[name] = self.words[i + 1]
            i += 2
        return cat

    def catalog_length(self, name):
        """Длина модуля в словах по записи каталога (поле 8*длина)."""
        rec = self.catalog[name]
        f = (rec >> 12) & 0xFFF
        return f // 8

    # --- объектные модули --------------------------------------------------
    def _header(self, s):
        w0, w1, w2 = self.words[s], self.words[s + 1], self.words[s + 2]
        return dict(head=w0 & M12, sym=(w0 >> 12) & M12, debug=w0 >> 36,
                    set_=w1 & M15, data=(w1 >> 15) & M15, long=(w1 >> 30) & M15,
                    cmd=w2 & M15, bss=(w2 >> 15) & M15, const=(w2 >> 30) & M15)

    def _find_objects(self):
        """Все объектные модули: имя -> (смещение, заголовок).

        Модули идут подряд, каждый начинается с границы 32 слов; начало
        следующего - не раньше конца разделов предыдущего (длина раздела
        `comment` неизвестна).  Оверлеи (ADAUGB, RCIF, ...) собственных
        объектов не имеют: это точки входа внутри базового модуля.
        """
        cands = []
        for s in range(2, self.nwords - 3):
            if s % 32:
                continue
            h = self._header(s)
            if h["head"] != 1:
                continue
            toff = s + 3 + h["cmd"] + h["const"] + h["data"] + h["set_"]
            if toff >= self.nwords:
                continue
            name = text_decode(self.words[toff]).rstrip()
            if name not in self.catalog:
                continue
            cands.append((s, name, h))
        objects = {}
        limit = 0
        for s, name, h in cands:
            if s < limit or name in objects:
                continue
            objects[name] = (s, h)
            limit = s + 3 + h["cmd"] + h["const"] + h["data"] + h["set_"] \
                + h["head"] + h["sym"] + h["long"] + h["debug"]
        return objects

    # --- разделы -----------------------------------------------------------
    def sections(self, name):
        """Смещения разделов объектного модуля (слова)."""
        s, h = self.objects[name]
        p = s + 3
        out = dict(header=s, cmd=p)
        p += h["cmd"]
        out["const"] = p
        p += h["const"]
        out["data"] = p
        p += h["data"]
        out["set"] = p
        p += h["set_"]
        out["head"] = p
        p += h["head"]
        out["sym"] = p
        p += h["sym"]
        out["long"] = p
        p += h["long"]
        out["debug"] = p
        p += h["debug"]
        out["comment"] = p
        out["end"] = p
        return out

    def code(self, name):
        """Слова команд модуля."""
        s, h = self.objects[name]
        return self.words[s + 3:s + 3 + h["cmd"]]


def main():
    args = sys.argv[1:]
    path = "siprod.bin"
    if args and not args[0].startswith("-"):
        path = args.pop(0)
    lib = Library(path)
    if args and args[0] == "--dump":
        name = args[1]
        s, h = lib.objects[name]
        sec = lib.sections(name)
        print(f"{name}: header @{s}, разделы:", sec)
        print(f"  cmd={h['cmd']} const={h['const']} bss={h['bss']} "
              f"data={h['data']} set={h['set_']} sym={h['sym']} "
              f"long={h['long']} debug={h['debug']}")
        print(f"  длина при загрузке: {h['cmd'] + h['const'] + h['bss']}")
        for i in range(sec["cmd"], sec["const"]):
            print(f"   {i:6d} {lib.words[i]:012x}")
        return
    print(f"слов в образе: {lib.nwords}, модулей в каталоге: {len(lib.catalog)},"
          f" найдено объектов: {len(lib.objects)}")
    for name in sorted(lib.objects):
        s, h = lib.objects[name]
        print(f"  {name:10s} @{s:6d} cmd={h['cmd']:5d} const={h['const']:5d} "
              f"bss={h['bss']:4d} sym={h['sym']:4d} long={h['long']:4d}")


if __name__ == "__main__":
    main()
