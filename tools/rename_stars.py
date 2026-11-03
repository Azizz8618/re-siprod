#!/usr/bin/env python3
"""Канонизация имён со звёздочками в текстах МАДЛЕН.

Внешние имена постоянной библиотеки и общие блоки в СИПРОДе записаны
со звёздочками: подпрограммы I*MU*I, I*DI*I, I*PO*I, FT*002, STOP* -
звёздочка внутри имени; общие блоки *INS*, *EGO*, *SCANER* - звёздочки
по краям.  При разборе дизассемблером часть имён потеряла звёздочки:

  * код SCAKOD/STAATP: объявления и вызовы I*MUI* - НЕ опечатка: это
    отдельная подпрограмма постоянной библиотеки, отличная от I*MU*I
    (в исходном объекте SCAKOD обе записи в разделе длинных имён,
    I*MUI* разрешается в картах загрузки: Дубна 55571, dispak 55367);
    имена в коде не трогаются;
  * шапки: усечённые имена IMUI, IDII, IPOI, FT002, SYTOBI вместо
    канона (в SCAKOD/STAATP в шапку добавлено и I*MUI*);
  * шапки: имена общих блоков без звёздочек (INS, EGO, NUSTA...), тогда
    как в коде они объявлены как *INS*, *EGO*...

Скрипт приводит имена к канону:

  * шапки (строки «C...»): IMUI -> I*MU*I, IDII -> I*DI*I,
    IPOI -> I*PO*I, FT002/003/541/571 -> FT*002..., SYTOBI -> SYTOBIN,
    STOP -> STOP*;
  * шапки (строки «Внешние:», «Смещения в ИМЯ:» и продолжения
    «Внешние:»): имена общих блоков - по фактическим объявлениям LC
    (INS -> *INS*, EGO -> *EGO* и т.д.);
  * SKZONA: объявляет входы SKZONA1024/SKZONA1040/SKZONA2 через EQU -
    в исходном объекте это ссылки СК+1024, СК+1024+16, СК+2 (таблица
    символов: 'ref' на символ 0), в тексте МАДЛЕН они потерялись, и
    ссылка UTC,SKZONA1024 оставалась неразрешённой.

Локальные метки (ВЫЗОВ_IMUI, INS24A, SYTOBA) не трогаются: замена идёт
по целым токенам, подчёркивание и цифры входят в токен.

Запуск: python3 tools/rename_stars.py [--dry]
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MADLEN = os.path.join(ROOT, "madlen")

# подпрограммы постоянной библиотеки и свои: усечённое имя -> канон
SUBP_MAP = {
    "IMUI": "I*MU*I",
    "IDII": "I*DI*I",
    "IPOI": "I*PO*I",
    "FT002": "FT*002",
    "FT003": "FT*003",
    "FT541": "FT*541",
    "FT571": "FT*571",
    "SYTOBI": "SYTOBIN",
    "STOP": "STOP*",
}
# код: имени не трогаем - I*MUI* оказалась отдельной подпрограммой
# постоянной библиотеки (см. шапку), а не опечаткой
CODE_MAP = {}

TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9*+._]+")
RE_LC = re.compile(r"^\s*([^\s,:]+)\s*:,LC,")
RE_EXTERN = re.compile(r"^CВнешние:")
RE_LCOFF = re.compile(r"^CСмещения в ")


def norm(name):
    """Имя без краевых звёздочек (для сопоставления с LC)."""
    return name.strip().strip("*").strip()


def module_decls(path):
    """Объявления модуля: (lc, subp, equ).

    lc   - нормализованное имя -> каноническая форма (*INS*);
    subp - сырые имена объявленных подпрограмм;
    equ  - имена, определённые через EQU.
    """
    lc, subp, equ = {}, set(), set()
    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        if line.startswith("C"):
            continue
        m = RE_LC.match(line)
        if m:
            lc.setdefault(norm(m.group(1)), m.group(1))
            continue
        m = re.match(r"^\s*([^\s,:]+)\s*:,SUBP,", line)
        if m:
            subp.add(m.group(1))
            continue
        m = re.match(r"^\s*([^\s,:]+)\s*:,EQU,", line)
        if m:
            equ.add(m.group(1))
    return lc, subp, equ


def map_namelist(txt, lc, subp, equ):
    """Строка списка имён (без ведущей C): канонизация токенов.

    Порядок: канон LC модуля; усечённые имена подпрограмм; снятие
    лишних звёздочек, если имя без них объявлено модулем (NUSTA -
    модуль, а *NUSTA* - чужой общий блок).
    """
    changes = []
    parts, last = [], 0
    for m in TOKEN_RE.finditer(txt):
        tok = m.group(0)
        new = None
        if tok in lc.values():
            pass
        elif norm(tok) in lc:
            new = lc[norm(tok)]
        elif tok in SUBP_MAP:
            new = SUBP_MAP[tok]
        elif (tok.startswith("*") and tok.endswith("*") and len(tok) > 2
                and (norm(tok) in subp or norm(tok) in equ)):
            new = norm(tok)
        parts.append(txt[last:m.start()])
        parts.append(new if new else tok)
        if new:
            changes.append((tok, new))
        last = m.end()
    parts.append(txt[last:])
    return "".join(parts), changes


def map_prose(txt):
    """Прочие строки шапки: только усечённые имена подпрограмм."""
    changes = []
    parts, last = [], 0
    for m in TOKEN_RE.finditer(txt):
        tok = m.group(0)
        new = SUBP_MAP.get(tok)
        parts.append(txt[last:m.start()])
        parts.append(new if new else tok)
        if new:
            changes.append((tok, new))
        last = m.end()
    parts.append(txt[last:])
    return "".join(parts), changes


def fix_skzona(text):
    """Входы SKZONA1024/SKZONA1040/SKZONA2 через EQU (если их ещё нет)."""
    if "SKZONA1024:,EQU," in text:
        return text, False
    lines = text.split("\n")
    out = []
    inserted = False
    for line in lines:
        out.append(line)
        if not inserted and re.match(r"^\s*SKZONA\s*:,NAME,", line):
            out += [
                "C ВХОДЫ МОДУЛЯ: в исходном объекте - ссылки на СК",
                "C (таблица символов: СК+1024, СК+1024+16, СК+2)",
                " SKZONA1024:,EQU,SKZONA+1024           .вход: СК+1024",
                " SKZONA1040:,EQU,SKZONA+1040           .вход: СК+1040",
                " SKZONA2  :,EQU,SKZONA+2               .вход: СК+2",
            ]
            inserted = True
    return "\n".join(out), inserted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true",
                    help="только показать замены")
    args = ap.parse_args()

    total = 0
    for fn in sorted(os.listdir(MADLEN)):
        if not fn.endswith(".madlen"):
            continue
        path = os.path.join(MADLEN, fn)
        text = open(path, encoding="utf-8").read()
        lc, subp, equ = module_decls(path)
        out_lines, log = [], []
        cont = False                 # продолжение списка «Внешние:»
        for line in text.split("\n"):
            if not line.startswith("C"):
                out_lines.append(line)   # код: имена не трогаем
                continue
            txt = line[1:]
            naked = txt.strip()
            if naked.startswith("Внешние:"):
                body = naked[len("Внешние:"):]
                new_body, changes = map_namelist(body, lc, subp, equ)
                cont = body.rstrip().endswith(",")
                out_lines.append("CВнешние:" + new_body)
            elif cont:
                if re.match(r"^(Выход:|Смещения|Абсолютные|Регистры|Вход:|"
                            r"Модификатор|Общие блоки)", naked):
                    cont = False
                    out_lines.append(line)
                    continue
                new_txt, changes = map_namelist(txt, lc, subp, equ)
                cont = txt.rstrip().endswith(",")
                out_lines.append("C" + new_txt)
            elif naked.startswith("Смещения в "):
                new_txt, changes = map_namelist(txt, lc, subp, equ)
                out_lines.append("C" + new_txt)
            else:
                new_txt, changes = map_prose(txt)
                out_lines.append("C" + new_txt)
            for old, nw in changes:
                log.append("  %s -> %s" % (old, nw))
        new_text, ins = fix_skzona("\n".join(out_lines))
        if fn == "SKZONA.madlen" and ins:
            log.append("  + входы SKZONA1024/SKZONA1040/SKZONA2 (EQU)")
        if log:
            print("%s:" % fn)
            for entry in log:
                print(entry)
            total += len(log)
            if not args.dry:
                open(path, "w", encoding="utf-8").write(new_text)
    print("итого замен: %d%s" % (total, " (сухой прогон)" if args.dry else ""))


if __name__ == "__main__":
    sys.exit(main())
