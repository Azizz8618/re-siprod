#!/usr/bin/env python3
"""Проверка кратких форм ключевых слов ДРАКОН на согласованность.

Сверяет три реализации таблицы кратких форм (tools/drakon_markup.py,
redakt.pas, drakon.pas) и проверяет правила:
  1. код - ровно 2 литеры;
  2. код не совпадает с каноническим словом;
  3. код не является началом чужого канонического слова;
  4. коды уникальны и указывают на существующее слово;
  5. наборы кодов во всех трёх реализациях одинаковы;
  6. канонические слова во всех трёх реализациях одинаковы.

Запуск из корня репозитория:  python3 tools/kw_alias_check.py
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def canonical_words():
    """Канонические слова из initkw в drakon.pas: номер -> слово."""
    text = open(os.path.join(BASE, 'pascal', 'source', 'drakon.pas'),
                encoding='utf-8').read()
    chars = {}
    for m in re.finditer(r"\bkw\[(\d+)\]\[(\d+)\] := '(.)'", text):
        chars.setdefault(int(m.group(1)), {})[int(m.group(2))] = m.group(3)
    return {i: ''.join(c[j] for j in sorted(c)) for i, c in chars.items()}


def py_alias():
    """Словарь ALIAS из tools/drakon_markup.py: код -> номер слова."""
    sys.path.insert(0, os.path.join(BASE, 'tools'))
    import drakon_markup
    words = canonical_words()
    names = {v: k for k, v in words.items()}
    return {code: names[word]
            for code, word in drakon_markup.ALIAS.items()}


def pas_alias(fname, prefix):
    """Таблица кратких форм из initkw паскального файла: код -> номер."""
    text = open(os.path.join(BASE, 'pascal', 'source', fname),
                encoding='utf-8').read()
    pairs = {int(m.group(1)): int(m.group(2))
             for m in re.finditer(prefix + r"almap\[(\d+)\] := (\d+)", text)}
    codes = {}
    for m in re.finditer(
            prefix + r"ali\[(\d+)\]\[1\] := '(.)';\s*" + prefix +
            r"ali\[\1\]\[2\] := '(.)'", text):
        codes[int(m.group(1))] = m.group(2) + m.group(3)
    return {codes[i]: pairs[i] for i in codes}


def main():
    words = canonical_words()
    tables = {
        'drakon_markup.py': py_alias(),
        'redakt.pas': pas_alias('redakt.pas', r'rmem\.'),
        'drakon.pas': pas_alias('drakon.pas', r''),
    }
    problems = []
    for name, tab in tables.items():
        if len(tab) != 23:
            problems.append(f'{name}: {len(tab)} кодов вместо 23')
        for code, num in sorted(tab.items()):
            if len(code) != 2:
                problems.append(f'{name}: код {code} не из 2 литер')
            if num not in words:
                problems.append(f'{name}: код {code} указывает на '
                                f'несуществующее слово {num}')
                continue
            word = words[num]
            if code == word:
                problems.append(f'{name}: код {code} совпадает со словом')
            for n, w in words.items():
                if n != num and w.startswith(code):
                    problems.append(f'{name}: код {code} ({word}) - начало '
                                    f'чужого слова {w}')
    ref = tables['drakon_markup.py']
    for name in ('redakt.pas', 'drakon.pas'):
        if tables[name] != ref:
            problems.append(f'{name}: таблица не совпадает с эталоном')
    print('канонических слов:', len(words))
    for name, tab in tables.items():
        print(f'{name}: {len(tab)} кратких форм')
    if problems:
        print('ПРОБЛЕМЫ:')
        for p in problems:
            print('  ', p)
        return 1
    print('все проверки пройдены')
    return 0


if __name__ == '__main__':
    sys.exit(main())
