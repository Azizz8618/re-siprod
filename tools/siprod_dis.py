#!/usr/bin/env python3
"""Дизассемблирование модулей СИПРОДа в автокод БЕМШ.

Разбор модуля и его таблицы символов делает `tools/siprod_lib.py`,
декодирование команд - внешний инструмент `disbesm6` (дизассемблер БЕМШ).

В адресном поле команд модуля DMS-формата бит 21 означает «структурированный»
(перемещаемый) адрес: при значении >= 074000 - ссылка на внешний символ
(номер в таблице символов = адрес & 03777), иначе - локальная метка
(смещение = адрес & 03777, в словах от начала раздела команд).  Имена
подставляются в листинг на месте.

Использование:
    tools/siprod_dis.py                 # все модули -> dis/
    tools/siprod_dis.py SCAN SPAUD      # только указанные модули
"""

import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from siprod_lib import Library, text_decode  # noqa: E402

# бит 21 адресного поля: адрес перемещаемый (формат DMS)
STRUCT_BIT = 0x200000
SYM_TAG = 0o7               # биты 14..12 адреса: ссылка на символ
LOC_TAG = 0o4               # биты 14..12 адреса: локальная метка


def symbol_table(lib, name):
    """Таблица символов модуля.

    Возвращает (names, labels):
      names  - словарь номер символа -> имя (внешние имена);
      labels - словарь смещение (в словах) -> имя локальной метки.
    """
    s, h = lib.objects[name]
    sec = lib.sections(name)
    table_off = sec["head"]
    words = lib.words
    symtab = [None] * (h["head"] + h["sym"])

    def sym_name(index):
        """Имя по номеру: слово с именем в разделе длинных имён
        (или короткое имя в старших битах слова таблицы символов)."""
        if table_off + index >= lib.nwords:
            return None
        w = words[table_off + index]
        if index >= h["head"] + h["sym"]:
            # длинное имя: всё слово - 8 символов TEXT
            return text_decode(w).rstrip() or None
        if w >> 42:                       # короткое имя в старших битах
            return text_decode(w & 0o77777777700000000).rstrip() or None
        return text_decode(w).rstrip() or None

    for i in range(h["head"], h["head"] + h["sym"]):
        w = words[sec["sym"] - h["head"] + i]
        kind = w & 0o57000000
        index = (w >> 24) & 0o3777
        if kind == 0o43000000:             # внешняя подпрограмма
            symtab[i] = ("subp", sym_name(index))
        elif kind == 0o47000000:          # общий блок
            symtab[i] = ("lc", sym_name(index), w & 0o777777)
        elif kind == 0o46000000:          # метка
            symtab[i] = ("lp", sym_name(index))
        elif (w >> 15) & 0o777 == 0o410:  # относительный адрес
            symtab[i] = ("rel", w & 0o7777)
        elif (w >> 15) & 0o777 == 0o400:  # абсолютный адрес
            symtab[i] = ("abs", w & 0o77777)
        else:                             # ссылка на символ + смещение
            symtab[i] = ("ref", index, w & 0o77777)

    names = {}
    labels = {}
    for i, e in enumerate(symtab):
        if e is None:
            continue
        if e[0] in ("subp", "lc", "lp") and e[1]:
            names[i] = e[1]
        elif e[0] == "rel":
            labels.setdefault(e[1], "L%04o" % e[1])
    # имена внешних символов нумеруются по номеру в таблице символов;
    # ссылка "символ + смещение" получает имя своего символа
    ext = {}
    for i, e in enumerate(symtab):
        if not e:
            continue
        if e[0] in ("subp", "lc", "lp") and e[1]:
            ext[i] = e[1]
        elif e[0] == "ref":
            base = symtab[e[1]] if e[1] < len(symtab) else None
            if base and base[0] in ("subp", "lc", "lp") and base[1]:
                ext[i] = "%s+%o" % (base[1], e[2])
    return ext, labels, symtab


def local_refs(code):
    """Смещения локальных меток, на которые ссылаются команды модуля."""
    refs = set()
    for w in code:
        for half in (w >> 24, w & 0xffffff):
            v = half & 0o77777
            if (v >> 12) & 7 == LOC_TAG:
                refs.add(v & 0o7777)
    return refs


def wrap(f, prefix, items, width=76):
    """Запись длинного перечня с переносом по строкам."""
    line = prefix
    for it in items.split(", "):
        if len(line) + len(it) + 2 > width and line != prefix:
            f.write(line + "\n")
            line = "; " + it + ", "
        else:
            line += ("" if line.endswith(" ") else " ") + it + ", "
    f.write(line.rstrip(", ") + "\n")


def disassemble(lib, name, outdir, disbesm6="disbesm6"):
    """Дизассемблирование одного модуля; возвращает имя файла листинга."""
    s, h = lib.objects[name]
    code = lib.words[s + 3:s + 3 + h["cmd"]]
    ext, labels, symtab = symbol_table(lib, name)
    # локальные метки, на которые ссылаются команды, но которые не названы
    # в таблице символов, получают автоматические имена
    for off in local_refs(code):
        labels.setdefault(off, "L%04o" % off)
    # начало модуля - его точка входа
    labels.setdefault(0, name)

    work = tempfile.mkdtemp(prefix="siprod-dis-")
    try:
        binf = os.path.join(work, "code.bin")
        with open(binf, "wb") as f:
            for w in code:
                f.write(w.to_bytes(6, "big"))
        # карта символов для disbesm6: все слова - точки входа (иначе
        # разбираются только достижимые команды), метки - с именами.
        # Адреса в модуле DMS считаются в командах (24 бита), в слове
        # две команды, поэтому метка попадает в слово offset//2.
        byword = {}
        for off, lab in labels.items():
            byword.setdefault(off // 2, []).append((off, lab))
        symf = os.path.join(work, "code.sym")
        with open(symf, "w") as f:
            for off in range(len(code)):
                labs = byword.get(off)
                f.write("%o 2 %s\n" % (off, "+".join(l for _, l in labs)
                                      if labs else "-"))
        out = subprocess.run([disbesm6, "-a0", "-e0", "-n" + symf, binf],
                             capture_output=True, text=True)
        listing = out.stdout
    finally:
        for f in os.listdir(work):
            os.unlink(os.path.join(work, f))
        os.rmdir(work)

    listing = resolve(lib, name, listing, code, ext, labels, symtab)
    listing = re.sub(r"^.*File: .*$", "; " + name + ": код модуля", listing,
                     flags=re.M)
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, name.replace("*", "#") + ".asm")
    with open(path, "w") as f:
        f.write("; %s - модуль СИПРОДа, автокод БЕМШ\n" % name)
        f.write("; разобрано disbesm6, объект в siprod.bin, слово %d\n" % s)
        f.write("; длина при загрузке: %d слов (%d команд)\n"
                % (h["cmd"] + h["bss"] + h["const"], h["cmd"] * 2))
        f.write("; адреса в командах (в слове две команды)\n")
        wrap(f, "; внешние символы: ",
             ", ".join("%s=%s" % (k, v) for k, v in sorted(ext.items())))
        wrap(f, "; локальные метки: ",
             ", ".join("%s=%o" % (v, k) for k, v in sorted(labels.items())))
        f.write(listing)
    return path


OPERAND = re.compile(r"\t('?[0-7]{5}'?)(?:\(М[0-9]+\))?\s*$")


def resolve(lib, name, listing, code, ext, labels, symtab):
    """Подстановка имён вместо перемещаемых адресов.

    disbesm6 печатает для каждого слова две строки: старшие и младшие
    24 бита (две команды в слове).  В каждой строке операнд - последнее
    поле; если адрес перемещаемый, вместо него подставляется имя.
    """
    res = []
    addr = None
    half = 0
    for line in listing.split("\n"):
        m = re.match(r"^(\s*)(\d+)(\s|$)", line)
        if m and not line.startswith("      "):
            addr = int(m.group(2), 8)      # адреса печатаются в восьмеричной
            half = 0
            res.append(subst(line, code[addr] >> 24 if addr < len(code) else 0,
                              ext, labels))
            continue
        m = re.match(r"^      (\d+) ", line)
        if m and addr is not None:
            res.append(subst(line, code[addr] & 0xffffff if addr < len(code)
                              else 0, ext, labels))
            continue
        res.append(line)
    return "\n".join(res)


def subst(line, half, ext, labels):
    """Замена операнда с перемещаемым адресом на имя символа.

    Адресное поле (15 бит) помечено битами 14..12: 4 - локальная метка
    (смещение в командах от начала модуля), 7 - внешний символ (номер
    записи в таблице символов).
    """
    value = half & 0o77777
    tag = (value >> 12) & 7
    name = None
    if tag == SYM_TAG:
        index = value & 0o3777
        name = ext.get(index, "СИМ%o" % index)
    elif tag == LOC_TAG:
        off = value & 0o7777
        name = labels.get(off, "*%04oB" % off)
    if name is None:
        return line
    return OPERAND.sub(lambda m: "\t" + name, line)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    opts = [a for a in sys.argv[1:] if a.startswith("-")]
    path = "siprod.bin"
    if args and os.path.exists(args[0]):
        path = args.pop(0)
    outdir = "dis"
    for o in opts:
        if o.startswith("--out="):
            outdir = o[6:]
    lib = Library(path)
    names = args if args else sorted(lib.objects)
    for name in names:
        if name not in lib.objects:
            print("нет модуля: %s" % name, file=sys.stderr)
            continue
        p = disassemble(lib, name, outdir)
        print("%-10s -> %s" % (name, p))


if __name__ == "__main__":
    main()
