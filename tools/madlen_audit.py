#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Аудит текстов Мадлен (madlen/*.madlen): перекрёстные ссылки и литералы.

Проверки перекрёстных ссылок между модулями:
  X1  имена-операнды, не объявленные в модуле (метки, общие блоки, SUBP,
      EQU) и не являющиеся числами, - «висячие» ссылки;
  X2  внешние процедуры (SUBP), которых нет ни в каталоге библиотеки
      СИПРОДа, ни среди известных имён постоянной библиотеки монитора;
  X3  общие блоки (LC), объявленные ровно одним модулем, - никто их
      не разделяет (возможно, имя записано не так, как в других);
  X4  общие блоки, объявленные в разных модулях с разными размерами;
  X5  SUBP, объявленный в модуле, но ни разу не вызванный;
  X6  общий блок, объявленный, но ни разу не использованный в коде;
  X7  расхождение шапки модуля («Внешние:») с фактическими объявлениями;
  X8  расхождение шапки («Выход:» - кто вызывает) с фактическим графом
      вызовов;
  X9  имена с абсолютным адресом (ЭКВ), нужные для ссылок на постоянную
      библиотеку, - объявлены ли.

Проверки литеральных смещений:
  L1  числовые операнды N(Мк) по регистрам: кадр М7 (<2048), каталог
      задачи (М7 2048..2159), вне кадра (М7 >= 2160), магазин/ОС (М12),
      контекст (М17), блок вызывающего (М10), индекс (М1) и прочие;
  L2  полнота шапки «Смещения в кадре (М7)» / «вне кадра»;
  L3  полнота шапок «Смещения в <ИМЯ>» относительно фактических
      обращений *ИМЯ*+N (необнаруженные ссылки на элементы блоков);
  L4  недешифрованные данные (ПЕРЕМЕННАЯ_*, КОД_*): используется ли
      в коде и стоит ли пометка «В КОДЕ НЕ ИСПОЛЬЗУЕТСЯ».

Запуск:
    python3 tools/madlen_audit.py            # полный отчёт
    python3 tools/madlen_audit.py --module SPAUD
    python3 tools/madlen_audit.py --json out.json
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MADLEN_DIR = os.path.join(ROOT, "madlen")

# Известные имена постоянной библиотеки монитора («Дубна») и системы,
# которых нет в каталоге личной библиотеки СИПРОДа (notes/linker.md 7.3).
PERMANENT_SUBP = {
    "I*MU*I", "I*MUI*", "I*DI*I", "I*PO*I", "FT*002", "FT*003",
    "FT*541", "FT*571", "STOP*",
    "FOR", "TYPE", "NUM", "WHO", "ONE", "COMCON", "JAU", "NOTF", "SAL",
    "VER", "NBR", "NEW", "HED", "NEWST", "REG", "IMA", "CEN", "ENDPUS",
    "LOADGO", "WDLIHA", "IDA", "ID1", "ID2", "ID3", "ID4", "ID5", "ID6",
    "ID7", "ID8", "ID9", "SIN", "COS", "EXP", "LN", "SQRT", "ATN",
    "DAZ", "DFIX", "DFLOT", "MOD",
}

# Мнемоники операций (dtran), у которых операнд - имя или число.
OPCODES = {
    "XTA", "XTS", "A+X", "A-X", "X-A", "AEX", "AAX", "AOX", "ASN", "LOG",
    "ITS", "ITA", "ATI", "STX", "STI", "MTJ", "UJ", "VJM", "VTM", "UTM",
    "U1A", "UZA", "VZM", "VLM", "WTC", "UTC", "J+M", "V1M", "ARX", "XMT",
    "YTA", "ASN", "AAX",
}
PSEUDOS = {"NAME", "LC", "SUBP", "EQU", "BSS", "INT", "ISO", "DATA", "END"}

RE_OCT = re.compile(r"^-?(\d+)[Bb]$")
RE_DEC = re.compile(r"^-?(\d+)$")
RE_NAME_OFF = re.compile(r"^([^+\-]+)([+-])(\d+[Bb]?)$")

# Каталог задачи Монитор-80: смещение -> имя (monitor80-re/permanent).
TASK_CATALOG_NAMES = {
    0: "каталог томов (RDCAT/WRCAT)",
    1: "word1 (нулевое слово)",
    2: "каталог временной библиотеки",
    16: "таблица страниц (PAGE=NCL=OCL)",
    80: "LWW",
    81: "SAV",
    83: "SAV1",
    1536: "конец секций (lastsect)",
}


def norm_name(n):
    """Нормализация имени общего блока/процедуры: без внешних звёздочек."""
    return n.strip().strip("*").strip()


def parse_value(tok):
    """Число (десятичное) или None. Форма: N, NB (восьмеричное), -N."""
    t = tok.strip()
    m = RE_OCT.match(t)
    if m:
        sign = -1 if t.startswith("-") else 1
        return sign * int(m.group(1), 8)
    m = RE_DEC.match(t)
    if m:
        return int(t)
    return None


class Module(object):
    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path).replace(".madlen", "")
        self.labels = set()          # локальные метки кода и данные
        self.lc = {}                 # имя(норм.) -> размер
        self.lc_raw = {}             # имя(норм.) -> имя как в тексте
        self.subp = {}               # имя как в тексте (без пробелов) -> оригинал
        self.equ = {}                # имя -> значение/имя
        self.bss = {}                # имя -> размер
        self.consts = {}             # имя -> значение (INT/ISO/данные)
        self.used = set()            # имена-операнды в командах
        self.used_lc = defaultdict(set)   # имя -> {смещения}
        self.calls = set()           # имена в VJM
        self.cmds = []               # (метка, модиф, оп, операнд, коммент)
        self.literals = []           # (модиф, значение, оп, коммент)
        self.hdr_extern = set()      # шапка «Внешние:»
        self.hdr_out = set()         # шапка «Выход:» (кто вызывает)
        self.hdr_lc_off = defaultdict(set)  # шапка «Смещения в ИМЯ»
        self.hdr_m7 = set()          # шапка «Смещения в кадре (М7)»
        self.hdr_outside = set()     # шапка «вне кадра»
        self._hdr_cont = False       # продолжение списка «Внешние:»
        self.data_names = {}         # имя -> {"used": bool, "note": bool}
        self.header_lines = []
        self._parse()

    # ----- разбор ----------------------------------------------------
    def _parse(self):
        with open(self.path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        in_data = False
        last_c_comment = ""
        for raw in lines:
            line = raw.rstrip("\n")
            if line.startswith("C"):
                self.header_lines.append(line[1:].strip())
                txt = line[1:].strip()
                if txt:
                    last_c_comment = txt
                self._parse_header(txt)
                continue
            if not line.strip():
                last_c_comment = ""
                continue
            # ISO-строки не режем по комментарию: '..' - часть операнда
            is_iso = ",ISO," in line
            if is_iso:
                comment = ""
                body = line
            else:
                # комментарий начинается с '.', за которым пробел или буква:
                # либо после пробелов ('... .переход на F9'),
                # либо прилегая к операнду ('...КОНСТА1.М16 := адрес К22')
                m = re.search(r"\s\.(?=\s|\S)", line)
                if not m:
                    m = re.search(r"\.(?=[А-ЯЁA-Zа-яa-z])", line)
                comment = line[m.end():].strip() if m else ""
                body = line[:m.start()] if m else line
            body = body.rstrip()
            if not body.strip():
                continue
            # раздел DATA/END
            if re.match(r"^\s*,\s*(DATA|END)\s*,\s*$", body):
                kind = re.match(r"^\s*,\s*(DATA|END)", body).group(1)
                in_data = kind == "DATA"
                continue
            # метка?
            label = None
            m = re.match(r"^\s*([^,:\s]+)\s*:", body)
            if m:
                label = m.group(1)
                body = body[m.end():]
                if label:
                    self.labels.add(label)
            fields = [f.strip() for f in body.split(",")]
            if len(fields) < 2:
                continue
            mod, op = fields[0], fields[1].upper()
            operand = ",".join(fields[2:]).strip() if len(fields) > 2 else ""
            if op in PSEUDOS:
                self._parse_pseudo(op, operand, label, last_c_comment)
                continue
            if in_data and op == "SET":
                if operand:
                    self._use_operand(operand)
                continue
            if in_data and op == "":
                # слово данных: операнд - адрес (ссылка)
                if operand:
                    self._use_operand(operand)
                continue
            if op not in OPCODES:
                continue
            self.cmds.append((label, mod, op, operand, comment))
            # использование имён
            if label and (operand == "" or True):
                pass
            if operand:
                self._use_operand(operand)
            if op == "VJM" and operand:
                # сытое имя: звёздочки значимы (I*MU*I и I*MUI* - разные
                # подпрограммы постоянной библиотеки)
                nm = operand.split("+")[0].split("-")[0].strip()
                self.calls.add(nm)
            # литералы; ITS/STI/MTJ/ATI/ITA - операнд-номер регистра,
            # а не адрес (ложные литералы)
            if operand and op not in ("ITS", "STI", "MTJ", "ATI", "ITA"):
                base = operand.split("+")[0].split("-")[0].strip()
                if (parse_value(base) is not None and
                        parse_value(operand.split("+")[0].split("-")[0].strip()) is not None):
                    val = parse_value(base)
                    off = operand[len(base):]
                    offv = parse_value(off[1:]) if off else 0
                    if off.startswith("-"):
                        val -= offv
                    else:
                        val += offv
                    self.literals.append((mod, val, op, comment))

    def _use_operand(self, operand):
        # имя+смещение или имя-смещение; «64+32» - арифметика, не ссылка
        m = RE_NAME_OFF.match(operand.strip())
        if m and parse_value(m.group(3)) is not None:
            name = m.group(1).strip()
            if parse_value(name) is not None:
                return  # числовое выражение (ASN 64+32)
            off = parse_value(m.group(3))
            if m.group(2) == "-":
                off = -off
            if name:
                self.used.add(name)
                self.used_lc[norm_name(name)].add(off)
                self._note_data_use(name)
            return
        tok = operand.strip()
        if parse_value(tok) is not None:
            return
        if not tok:
            return
        self.used.add(tok)
        self.used_lc[norm_name(tok)].add(0)
        self._note_data_use(tok)

    def _note_data_use(self, name):
        if name in self.data_names:
            self.data_names[name]["used"] = True

    def _parse_pseudo(self, op, operand, label, comment):
        if not label:
            return
        nm = label.strip()
        if op == "LC":
            size = parse_value(operand.split()[0]) if operand else 0
            self.lc[norm_name(nm)] = size or 0
            self.lc_raw[norm_name(nm)] = nm
        elif op == "SUBP":
            self.subp[nm.strip()] = nm
        elif op == "EQU":
            self.equ[nm] = operand
        elif op == "BSS":
            size = parse_value(operand.split()[0]) if operand else 0
            self.bss[nm] = size or 0
            self.data_names[nm] = {"used": False, "note": False}
        elif op in ("INT", "ISO"):
            self.consts[nm] = operand
            self.data_names[nm] = {
                "used": False,
                "note": "НЕ ИСПОЛЬЗУЕТСЯ" in (comment or "").upper(),
            }

    def _add_hdr_extern(self, s):
        """Список «Внешние:» (или его продолжение): сырые имена."""
        for tok in s.split(","):
            tok = tok.strip()
            if tok:
                self.hdr_extern.add(tok)

    def _parse_header(self, txt):
        m = re.match(r"^Внешние:\s*(.*)", txt)
        if m:
            self._add_hdr_extern(m.group(1))
            self._hdr_cont = m.group(1).rstrip().endswith(",")
            return
        if self._hdr_cont:
            # продолжение списка «Внешние:» - строка имён через запятую;
            # любое другое поле шапки прекращает продолжение
            if re.match(r"^(Выход:|Смещения|Абсолютные|Регистры|Вход:|"
                        r"Модификатор|Общие блоки)", txt):
                self._hdr_cont = False
            else:
                self._add_hdr_extern(txt)
                self._hdr_cont = txt.rstrip().endswith(",")
                return
        if re.match(r"^Внешние\s*$", txt):
            self._hdr_cont = True
            return
        m = re.match(r"^Выход:\s*(.*)", txt)
        if m:
            for tok in re.split(r"[,\s]+", m.group(1)):
                base = tok.split(":")[0].strip()
                # только имена модулей (латиница верхнего регистра):
                # проза «(возврат через М15)» не имя
                if re.match(r"^[A-Z][A-Z0-9*_]*$", base):
                    self.hdr_out.add(norm_name(base))
            return
        m = re.match(r"^Смещения в ([^:]+):\s*(.*)", txt)
        if m:
            whom = norm_name(m.group(1))
            for tok in m.group(2).split(","):
                tok = tok.strip()
                if tok and parse_value(tok) is not None:
                    self.hdr_lc_off[whom].add(parse_value(tok))
            return
        m = re.match(r"^Смещения в кадре \(М7\):\s*(.*)", txt)
        if m:
            self.hdr_m7 |= self._parse_ranges(m.group(1))
            return
        m = re.match(r"^вне кадра\s+(.*)", txt)
        if m:
            self.hdr_outside |= self._parse_ranges(m.group(1))
            return

    @staticmethod
    def _parse_ranges(s):
        out = set()
        for tok in re.split(r"[,\s]+", s):
            tok = tok.strip()
            if not tok:
                continue
            m = re.match(r"^(\d+)-(\d+)$", tok)
            if m:
                out |= set(range(int(m.group(1)), int(m.group(2)) + 1))
            elif parse_value(tok) is not None:
                out.add(int(tok))
        return out

    # ----- классификация литералов -----------------------------------
    def classify_literals(self):
        """-> dict bucket -> список (значение, оп, коммент)."""
        buckets = defaultdict(list)
        for mod, val, op, comment in self.literals:
            reg = mod.strip()
            if reg in ("", "M7"):
                if 2048 <= val < 2160:
                    buckets["каталог задачи"].append((val, op, comment))
                elif val >= 2160:
                    buckets["вне кадра М7"].append((val, op, comment))
                else:
                    buckets["кадр М7"].append((val, op, comment))
            elif reg == "M12":
                buckets["магазин/ОС М12"].append((val, op, comment))
            elif reg == "M17":
                buckets["контекст М17"].append((val, op, comment))
            elif reg == "M10":
                buckets["блок вызывающего М10"].append((val, op, comment))
            elif reg == "M1":
                buckets["индекс М1"].append((val, op, comment))
            elif reg in ("M15", "M16", "M2", "M11", "M13", "M14"):
                buckets["прочие " + reg].append((val, op, comment))
            else:
                buckets["регистр " + (reg or "-")].append((val, op, comment))
        return buckets


def load_all():
    mods = []
    for fn in sorted(os.listdir(MADLEN_DIR)):
        if fn.endswith(".madlen"):
            mods.append(Module(os.path.join(MADLEN_DIR, fn)))
    return mods


def load_catalog():
    """Каталог модулей и таблицы символов объектов (сырые имена)."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    names = set()
    try:
        from siprod_lib import Library
        lib = Library(os.path.join(ROOT, "siprod.bin"))
        names |= set(k.strip() for k in lib.catalog)
        from siprod_dis import symbol_table
        for mod in lib.objects:
            try:
                _ext, _labels, symtab = symbol_table(lib, mod)
            except Exception:
                continue
            for e in symtab:
                if e and e[0] in ("subp", "lc") and e[1]:
                    names.add(e[1].strip())
    except Exception as e:  # библиотека не найдена - работаем без неё
        print("нет каталога библиотеки: %s" % e, file=sys.stderr)
    return names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--module", help="только этот модуль")
    ap.add_argument("--json", help="сохранить отчёт в JSON")
    args = ap.parse_args()

    mods = load_all()
    by_name = {m.name: m for m in mods}
    catalog = load_catalog()

    if args.module:
        mods = [m for m in mods if m.name == args.module]

    out = {"modules": {}, "summary": {}}
    P = print

    # ============ X: перекрёстные ссылки =============================
    P("=" * 72)
    P("X. ПЕРЕКРЁСТНЫЕ ССЫЛКИ МЕЖДУ МОДУЛЯМИ")
    P("=" * 72)

    # universe имён
    all_lc = defaultdict(dict)     # имя(норм.) -> {модуль: размер}
    all_subp = defaultdict(list)   # имя(сырое) -> [модули]
    for m in by_name.values():
        for nm, sz in m.lc.items():
            all_lc[nm][m.name] = sz
        for nm in m.subp:
            all_subp[nm].append(m.name)

    # сырые имена (как в таблицах символов объектов) - против ложных
    # срабатываний на именах с внутренними звёздочками (I*MUI*, STOP*)
    known_names = catalog | set(all_subp) | PERMANENT_SUBP
    known_lc_norm = set(all_lc) | set(norm_name(n) for n in catalog)

    x1, x2, x3, x4, x5, x6, x7, x8 = [], [], [], [], [], [], [], []
    for m in mods:
        # X1: использованные, но не объявленные имена
        undeclared = sorted(
            n for n in m.used
            if n not in m.labels and n not in m.equ and n not in m.bss
            and n not in m.consts and n not in m.subp
            and norm_name(n) not in m.lc
            and norm_name(n) not in known_lc_norm
            and n not in known_names
        )
        if undeclared:
            x1.append((m.name, undeclared))
        # X2: SUBP без владельца (сырые имена против таблиц символов)
        unknown_subp = sorted(n for n in m.subp if n not in known_names)
        if unknown_subp:
            x2.append((m.name, unknown_subp))
        # X5: SUBP объявлен, но не вызван
        unused_subp = sorted(n for n in m.subp if n not in m.calls)
        if unused_subp:
            x5.append((m.name, unused_subp))
        # X6: LC объявлен, но не использован
        unused_lc = sorted(n for n in m.lc if not m.used_lc.get(n))
        if unused_lc:
            x6.append((m.name, unused_lc))
        # X7: шапка «Внешние:» - сравнение сырых имён: звёздочки значимы
        # (I*MU*I и I*MUI* - разные подпрограммы), общие блоки - в форме
        # объявлений (*INS*)
        actual_ext = set(m.lc_raw.values()) | set(m.subp)
        missing_hdr = sorted(actual_ext - m.hdr_extern)
        extra_hdr = sorted(n for n in m.hdr_extern
                           if n not in actual_ext
                           and n not in m.equ)
        if missing_hdr or extra_hdr:
            x7.append((m.name, missing_hdr, extra_hdr))

    # X3: LC одного модуля
    for nm, owners in sorted(all_lc.items()):
        if len(owners) == 1:
            x3.append((nm, list(owners), list(owners.values())))
    # X4: расхождение размеров
    for nm, owners in sorted(all_lc.items()):
        sizes = set(owners.values())
        if len(sizes) > 1:
            x4.append((nm, owners))

    P("\nX1. Имена-операнды, не объявленные в модуле (%d модулей):" % len(x1))
    for name, lst in x1:
        P("  %-8s %s" % (name, ", ".join(lst)))
    if not x1:
        P("  - нет")

    P("\nX2. SUBP вне каталога библиотеки и постоянной библиотеки (%d):" % len(x2))
    for name, lst in x2:
        P("  %-8s %s" % (name, ", ".join(lst)))
    if not x2:
        P("  - нет")

    P("\nX3. Общие блоки, объявленные ровно одним модулем (%d):" % len(x3))
    for nm, owners, sizes in x3:
        P("  %-12s только в %s (%d слов)" % (nm, ", ".join(owners), sizes[0]))
    if not x3:
        P("  - нет")

    P("\nX4. Общие блоки с разными размерами в модулях (%d):" % len(x4))
    for nm, owners in x4:
        P("  %-12s %s" % (nm, owners))
    if not x4:
        P("  - нет")

    P("\nX5. SUBP объявлен, но не вызван в модуле (%d):" % len(x5))
    for name, lst in x5:
        P("  %-8s %s" % (name, ", ".join(lst)))
    if not x5:
        P("  - нет")

    P("\nX6. Общий блок объявлен, но не использован (%d):" % len(x6))
    for name, lst in x6:
        P("  %-8s %s" % (name, ", ".join(lst)))
    if not x6:
        P("  - нет")

    P("\nX7. Шапка «Внешние:» не совпадает с объявлениями (%d):" % len(x7))
    for name, missing, extra in x7:
        if missing:
            P("  %-8s нет в шапке: %s" % (name, ", ".join(missing)))
        if extra:
            P("  %-8s лишнее в шапке: %s" % (name, ", ".join(extra)))
    if not x7:
        P("  - нет")

    # X8: граф вызовов против шапки «Выход:»
    callers = defaultdict(set)   # кого зовут -> кто зовёт
    for m in by_name.values():
        for callee in m.calls:
            callers[callee].add(m.name)
    for m in mods:
        real = sorted(callers.get(norm_name(m.name), set()))
        claimed = sorted(m.hdr_out)
        if real != claimed:
            x8.append((m.name, claimed, real))
    P("\nX8. Шапка «Выход:» (кто вызывает) не совпадает с графом (%d):" % len(x8))
    for name, claimed, real in x8:
        only_claimed = sorted(set(claimed) - set(real))
        only_real = sorted(set(real) - set(claimed))
        if only_claimed:
            P("  %-8s в шапке, но не вызывают: %s" % (name, ", ".join(only_claimed)))
        if only_real:
            P("  %-8s вызывают, но нет в шапке: %s" % (name, ", ".join(only_real)))
    if not x8:
        P("  - нет")

    # ============ L: литеральные смещения ============================
    P()
    P("=" * 72)
    P("L. ЛИТЕРАЛЬНЫЕ СМЕЩЕНИЯ")
    P("=" * 72)

    lit_all = defaultdict(lambda: defaultdict(set))  # bucket -> знач -> модули
    for m in mods:
        for bucket, vals in m.classify_literals().items():
            for val, op, comment in vals:
                lit_all[bucket][val].add(m.name)

    P("\nL1. Каталог задачи (М7 2048..2159), элемент -> модули:")
    for val in sorted(lit_all["каталог задачи"]):
        el = val - 2048
        kn = TASK_CATALOG_NAMES.get(el, "?")
        P("  +%4d (=%d)  %-32s %d модулей: %s" % (
            el, val, kn, len(lit_all["каталог задачи"][val]),
            ", ".join(sorted(lit_all["каталог задачи"][val])) if
            len(lit_all["каталог задачи"][val]) <= 6 else
            ", ".join(sorted(lit_all["каталог задачи"][val])[:6]) + " …"))

    for bucket in ("кадр М7", "вне кадра М7", "магазин/ОС М12", "контекст М17",
                   "блок вызывающего М10", "индекс М1"):
        if not lit_all[bucket]:
            continue
        P("\nL1. %s (%d значений):" % (bucket, len(lit_all[bucket])))
        for val in sorted(lit_all[bucket]):
            mods_v = sorted(lit_all[bucket][val])
            P("  %6d   %2d мод.: %s" % (val, len(mods_v),
              ", ".join(mods_v[:8]) + (" …" if len(mods_v) > 8 else "")))

    # L2: полнота шапки кадра
    P("\nL2. Полнота шапки «Смещения в кадре (М7)» / «вне кадра»:")
    bad = 0
    for m in mods:
        lit_m7 = set()
        lit_out = set()
        for mod, val, op, comment in m.literals:
            if mod.strip() in ("", "M7"):
                if 2048 <= val < 2160:
                    lit_out.add(val)
                elif val >= 2160:
                    lit_out.add(val)
                else:
                    lit_m7.add(val)
        miss_frame = sorted(lit_m7 - m.hdr_m7)
        miss_out = sorted(lit_out - m.hdr_outside)
        if miss_frame or miss_out:
            bad += 1
            if miss_frame:
                P("  %-8s нет в шапке (кадр): %s" %
                  (m.name, ", ".join(map(str, miss_frame))))
            if miss_out:
                P("  %-8s нет в шапке (вне кадра): %s" %
                  (m.name, ", ".join(map(str, miss_out))))
    if not bad:
        P("  - расхождений нет")

    # L3: полнота шапок «Смещения в ИМЯ»
    P("\nL3. Обращения *ИМЯ*+N, не указанные в шапке «Смещения в ИМЯ»:")
    bad = 0
    for m in mods:
        for nm, offs in sorted(m.used_lc.items()):
            if not nm:
                continue
            hdr = m.hdr_lc_off.get(nm, None)
            if hdr is None:
                # блок может обозначаться и без звёздочек
                hdr = m.hdr_lc_off.get(nm.strip("*"), set())
                if not hdr and nm.startswith("*"):
                    continue  # шапки нет вообще - не расхождение
                if not hdr:
                    hdr = set()
            miss = sorted(offs - hdr)
            if miss:
                bad += 1
                P("  %-8s %s: нет в шапке смещения %s" %
                  (m.name, nm, ", ".join(map(str, miss))))
    if not bad:
        P("  - расхождений нет")

    # L4: недешифрованные данные
    P("\nL4. Недешифрованные данные (ПЕРЕМЕННАЯ_*/КОД_*):")
    re_undec = re.compile(r"^(ПЕРЕМЕ\d*ННАЯ_|КОНСТА\d*НТА_|КОД_)\d+$")
    tot_used = tot_note = tot_bad = 0
    per_mod = []
    for m in mods:
        u = n = b = 0
        for nm, info in m.data_names.items():
            if not re_undec.match(nm):
                continue
            tot_used += 1 if info["used"] else 0
            tot_note += 1 if info["note"] else 0
            u += 1 if info["used"] else 0
            n += 1 if info["note"] else 0
            if info["used"] and info["note"]:
                b += 1
                tot_bad += 1
        if u or n:
            per_mod.append((m.name, u, n, b))
    P("  недешифрованных имён: %d, используются в коде: %d, "
      "с пометкой «НЕ ИСПОЛЬЗУЕТСЯ»: %d" % (
          sum(1 for m in mods for nm in m.data_names
              if re_undec.match(nm)), tot_used, tot_note))
    if tot_bad:
        P("  ВНИМАНИЕ: помечены «не используется», но используются (%d):" % tot_bad)
        for name, u, n, b in per_mod:
            if b:
                P("    %-8s %d" % (name, b))

    # ============ сводка =============================================
    P()
    P("=" * 72)
    P("СВОДКА")
    P("=" * 72)
    P("модулей: %d, общих блоков: %d, внешних процедур: %d" %
      (len(by_name), len(all_lc), len(all_subp)))
    out["summary"] = {
        "modules": len(by_name),
        "common_blocks": len(all_lc),
        "subp": len(all_subp),
        "x1_undeclared": sum(len(l) for _, l in x1),
        "x2_unknown_subp": sum(len(l) for _, l in x2),
        "x3_single_lc": len(x3),
        "x4_size_mismatch": len(x4),
        "x5_unused_subp": sum(len(l) for _, l in x5),
        "x6_unused_lc": sum(len(l) for _, l in x6),
        "x7_hdr_extern": len(x7),
        "x8_hdr_out": len(x8),
    }
    P("нарушений: %s" % json.dumps(out["summary"], ensure_ascii=False))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        P("JSON: %s" % args.json)


if __name__ == "__main__":
    main()
