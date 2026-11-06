#!/usr/bin/env python3
"""Сравнение выдачи транслятора drakon.pas (БЭСМ-6) с эталоном.

Разметка */*D/*D -> сырые строки рисунка (склейка продолжений),
нормировка гомоглифов Е/E (в ИСО-Дубне латиница и кириллица делят
коды), сравнение с рисунком .txt.
usage: сверить-дракон.py <выдача-программы> <эталон.txt>
"""
import sys


def norm(s):
    # в ГОСТ-10859 нет строчных и знака вопроса (библиотека печатает
    # градус); Ё недоступна при наборе и заменяется Е
    table = str.maketrans({
        "Е": "E", "О": "O", "Р": "P", "А": "A", "С": "C",
        "Х": "X", "Т": "T", "В": "B", "М": "M", "Н": "H",
        "К": "K", "У": "Y",
        "?": "°",
        "Ё": "E",
    })
    return s.upper().translate(table)


def markup_to_rows(lines):
    out = []
    for l in lines:
        if l.startswith("*/*D"):
            out.append(l[4:])
        elif l.startswith("*D"):
            # перфокарта несёт 78 литер: хвостовые пробелы срезаны
            # печатающим устройством - восстанавливаем длину
            if out:
                out[-1] = out[-1].ljust(76) + l[2:]
    if out:
        return out
    # иначе это уже сырые строки рисунка
    return list(lines)


def main():
    prog, etalon = sys.argv[1], sys.argv[2]
    src = open(prog, errors="replace").read().splitlines()
    # программная выдача: после последней *EXECUTE до КОНЕЦ ЗАДАЧИ
    start = 0
    for i, l in enumerate(src):
        if l.strip() in ("*ЕХЕСUТЕ", "*EXECUTE"):
            start = i + 1
    end = len(src)
    for i in range(start, len(src)):
        if "КОНЕЦ ЗАДАЧИ" in src[i]:
            end = i
            break
    # ширина бумаги АЦПУ-128: строки длиннее 128 позиций обрезаются
    mine = [r[:128].rstrip() for r in markup_to_rows([norm(l) for l in src[start:end]])]
    ref = [r[:128].rstrip() for r in markup_to_rows([norm(l) for l in open(etalon, errors="replace").read().splitlines()])]
    # хвостовые пустые строки не сравниваем
    while mine and not mine[-1].strip():
        mine.pop()
    while ref and not ref[-1].strip():
        ref.pop()
    if mine == ref:
        print("СОВПАДАЕТ (%d строк)" % len(ref))
        return 0
    bad = 0
    for i in range(max(len(mine), len(ref))):
        a = mine[i] if i < len(mine) else "<нет>"
        b = ref[i] if i < len(ref) else "<нет>"
        if a != b:
            bad += 1
            if bad <= 8:
                print(f"строка {i+1}:")
                print(f"  МОЯ: {a!r}")
                print(f"  ЭТАЛ:{b!r}")
    print("РАЗЛИЧИЙ:", bad, "из", max(len(mine), len(ref)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
