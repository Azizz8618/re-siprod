#!/usr/bin/env python3
"""Правила имён идентификаторов DMS.

Компилятор МАДЛЕН (ДТРАН) обрезает идентификатор до 8 букв и цифр
(подчёркивания и знаки «+» в имя идентификатора не входят).  Поэтому
«РАЗБОР_КОМАНДЫ» и «РАЗБОР_КОМАНДЫ_2» для ДТРАН - одно и то же имя,
и сборка модуля обрывается с ошибкой «ДВАЖДЫ ОПИСАННЫЙ ИДЕНТИФИКАТОР».
Кроме того, в имени метки не допускается знак «+».

Отсюда два правила:
  * имя метки - не длиннее восьми букв и цифр подряд (без «+»);
  * никакие два идентификатора модуля не должны совпадать после
    обрезки.
"""

from __future__ import annotations

DMS_ID_LEN = 8


def dms_id(name):
    """Идентификатор DMS: первые 8 букв и цифр имени."""
    return "".join(ch for ch in name if ch.isalnum())[:DMS_ID_LEN]


def variant(name, n):
    """Имя с отличающимся началом: цифра вставляется после первого слова.

    «РАЗБОР_КОМАНДЫ» -> «РАЗБОР2_КОМАНДЫ»: обрезка до 8 знаков даёт
    «РАЗБОР2КО» - уже другое имя.
    """
    word = name.split("_")[0]
    # цифра ставится внутрь первого слова: обрезка до 8 знаков должна
    # дать другой идентификатор
    pos = min(max(len(word), 1), DMS_ID_LEN - 2)
    return name[:pos] + str(n) + name[pos:]


def unique(base, used, used_ids=None):
    """Свободное имя: и целиком, и по обрезке идентификатора DMS."""
    if used_ids is None:
        used_ids = used
    if base not in used and dms_id(base) not in used_ids:
        return base
    for n in range(2, 1000):
        cand = variant(base, n)
        if cand not in used and dms_id(cand) not in used_ids:
            return cand
    return base
