#!/usr/bin/env python3
"""Имена меток модулей СИПРОДа по содержанию кода.

Общая часть инструментов разбора текстов МАДЛЕН: и имена меток
(tools/siprod_madlen_labels.py), и пояснения к ним
(tools/siprod_madlen_notes.py) должны знать одно и то же имя метки,
поэтому вычисление имён вынесено сюда.

Имя метки выводится из содержимого блока команд, который начинается
меткой: вызов внешней подпрограммы, обращение к общему блоку, работа с
переменной модуля, возврат по М15 или роль первой операции блока.
Ручные имена (LABEL_NAMES) выигрывают у автоматических.
"""

from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from siprod_be import decode, info, operand_text          # noqa: E402
from siprod_lib import Library                             # noqa: E402


# Ручные имена меток: модуль -> {номер слова (восьмеричный): имя}.
# Номер слова - как в таблице символов DMS (слово от начала модуля).
# Имена осмысленные: отражают назначение процедуры, установленное по
# журналу опытов (notes/commands.md) и по справочнику SIPROD.md.
LABEL_NAMES = {
    # SPAUD - диспетчер команд режима *RED.  Адреса ветвей - из
    # notes/commands.md (таблица ветвей разбора *-команд); в скобках -
    # что делает ветвь.
    "SPAUD": {
        0o375: "ВЕТКА_F", 0o434: "ВЕТКА_T", 0o441: "ВЕТКА_S",
        0o555: "ВЕТКА_СЛЭШ", 0o611: "ВЕТКА_G", 0o652: "ВЕТКА_P",
        0o677: "ВЕТКА_E", 0o731: "ВЕТКА_ЗВЕЗДА", 0o735: "ВЕТКА_C",
        0o764: "ВЕТКА_H", 0o1014: "ВЕТКА_D", 0o1027: "ВЕТКА_N",
        0o1070: "ВЕТКА_O", 0o1227: "ВЕТКА_W", 0o1267: "ВЕТКА_M",
        0o1756: "ВЕТКА_R", 0o2201: "ВЕТКА_КОНЕЦ", 0o2242: "ВЕТКА_K",
        0o2333: "ВЕТКА_ЦИФРА", 0o2347: "ВЫХОД_ИЗ_SPAUD",
    },
    # SCHEMA - верхний уровень: разбор блоков и выбор обработчика.
    "SCHEMA": {
        0: "ГЛАВНАЯ",
        0o15: "ЧТЕНИЕ_РЕЖИМА",
        0o50: "ЗАПРОС_СТРОКИ",
        0o55: "РАЗБОР_КОМАНДЫ",
        0o70: "ЧТЕНИЕ_СИМВОЛА",
        0o117: "ОШИБКА_БЛОКА",
        0o156: "РАЗБОР_КОМАНДЫ_2",
        0o171: "ВЫВОД_СИСТЕМЫ",
        0o234: "ПРОВЕРКА_ФОРМАТА",
        0o272: "ФОРМИРОВАНИЕ_СТРАНИЦЫ",
        0o273: "КОНЕЦ_СТРАНИЦЫ",
        0o305: "ЗАПИСЬ_РЕДАКТОРА",
        0o437: "ЗАПИСЬ_РЕДАКТОРА_2",
        0o447: "КОНЕЦ_БЛОКА",
        0o476: "ЗАГРУЗКА_ОВЕРЛЕЯ",
        0o504: "ЗАГРУЗКА_ОВЕРЛЕЯ_2",
        0o507: "ЗАГРУЗКА_ОВЕРЛЕЯ_3",
        0o517: "ПРОВЕРКА_ФОРМАТА_2",
        0o535: "КОНЕЦ_СТРАНИЦЫ_2",
        0o547: "ВЫВОД_ТЕКСТА",
        0o551: "ЗАГРУЗКА_ОВЕРЛЕЯ_4",
        0o565: "ЗАПИСЬ_РЕДАКТОРА_3",
        0o602: "ВЫЗОВ_SPAUD",
    },
    # SCAN - разбор символа после '*'.
    "SCAN": {
        0: "ГЛАВНАЯ",
        0o1: "ЧТЕНИЕ_КОДA",
        0o22: "ПРОВЕРКА_КОДA",
        0o24: "ЧТЕНИЕ_ПАРАМЕТРА",
        0o63: "БЛОК_ПРОДОЛЖЕНИЕ",
        0o70: "ВОЗВРАТ_ИЗ_МОДУЛЯ",
    },
    # REDTXT - передача текста разбору команд SPAUD.
    "REDTXT": {
        0: "ГЛАВНАЯ",
        0o1: "ЧТЕНИЕ_РЕЖИМА",
        0o5: "ПЕРЕДАЧА_СКАНЕРУ",
        0o15: "БЛОК_ПРОДОЛЖЕНИЕ",
        0o16: "ОШИБКА_ВЫВОДА",
        0o22: "ПРОВЕРКА_КОМАНДЫ",
        0o23: "ЧТЕНИЕ_КОМАНДЫ",
        0o30: "ВОЗВРАТ_ИЗ_МОДУЛЯ",
    },
    # KLAIDA - вывод сообщения об ошибке.
    "KLAIDA": {
        0: "ГЛАВНАЯ",
        0o1: "ПОДГОТОВКА_СООБЩЕНИЯ",
        0o12: "ЧТЕНИЕ_НОМЕРА_ОШИБКИ",
        0o21: "ПЕЧАТЬ_СООБЩЕНИЯ",
        0o27: "ВОЗВРАТ_ИЗ_МОДУЛЯ",
    },
}


def role_of(instr):
    """Роль операции в коде - по ней называется блок."""
    return {
        "СЧИМ": "В МАГАЗИН", "СЧМ": "В МАГАЗИН", "УИМ": "ИЗ МАГАЗИНА",
        "РЖА": "ПЕРЕХОД", "ПО": "СРАВНЕНИЕ", "ПЕ": "СРАВНЕНИЕ",
        "ПБ": "ПЕРЕХОД", "УИА": "АДРЕС", "СЧ": "ЧТЕНИЕ", "ЗП": "ЗАПИСЬ",
        "ЗПМ": "ЗАПИСЬ", "СЛИА": "СЧЁТ", "СЛИ": "СЧЁТ", "И": "И",
        "ИЛИ": "ИЛИ", "НТЖ": "ИСКЛЮЧАЮЩЕЕ ИЛИ", "ВЧ": "ВЫЧИТАНИЕ",
        "ВЧОБ": "ВЫЧИТАНИЕ", "СЛ": "СЛОЖЕНИЕ", "СЛЦ": "СЛОЖЕНИЕ",
        "МОДА": "КАДР", "МОД": "КАДР", "СЧИ": "ЧТЕНИЕ РЕГ.",
        "УИ": "ЗАПИСЬ РЕГ.", "СЧРЖ": "ЧТЕНИЕ СЛОВА", "СЧМРЖ": "УМНОЖЕНИЕ",
        "СДА": "СДВИГ", "ЗНАК": "СМЕНА ЗНАКА", "ДЕЛ": "ДЕЛЕНИЕ",
        "УМН": "УМНОЖЕНИЕ", "Ц": "ЦИКЛ",
    }.get(instr, "ПРОЦЕДУРА")


def sanitize(s):
    """Имя символа пригодно для метки МАДЛЕН: буквы, цифры, подчёркивание."""
    s = "".join(ch for ch in s.upper() if ch.isalnum() or ch == "_")
    s = s.strip("_")
    if not s:
        return "СИМВОЛ"
    if s[0].isdigit():
        s = "С" + s
    return s[:24]


def unique(base, used):
    """Свободное имя: к основе добавляется номер."""
    if base not in used:
        return base
    for n in range(2, 1000):
        cand = "%s_%d" % (base, n)
        if cand not in used:
            return cand
    return base


def module_table(lib, name):
    """Имена меток модуля: номер слова -> имя.

    Разбор модуля (info) даёт команды и метки в номерах команд; в
    текстах МАДЛЕН метки названы номером слова, поэтому имена
    считаются по номеру слова (номер команды пополам).
    """
    ext, labels, exits, insns = info(lib, name)
    cmdwords = lib.objects[name][1]["cmd"]
    known = sorted(labels)
    byoff = {off: half for off, half in insns}
    manual = LABEL_NAMES.get(name, {})

    # признаки каждого блока: вызовы, общие блоки, локальные переменные,
    # переход (куда и назад ли) и число команд в блоке
    feats = {}
    for i, off in enumerate(known):
        nxt = known[i + 1] if i + 1 < len(known) else None
        calls, commons, locs = [], [], []
        ret = jump = back = False
        count = 0
        for o, half in insns:
            if o < off:
                continue
            if nxt is not None and o >= nxt:
                break
            count += 1
            dec = decode(half)
            instr = (dec["name"] or "").upper()
            op = operand_text(dec, ext, labels, name)
            if instr == "ПВ":
                calls.append(op.split("(")[0])
            elif instr in ("МОДА", "МОД") and op:
                base = op.split("(")[0]
                if base not in (name, "0"):
                    commons.append(base)
            elif instr in ("СЧ", "ЗП", "ЗПМ") and op:
                m = re.match(r"^(\d+)\(М7\)$", op)
                if m:
                    locs.append(m.group(1))
            elif instr == "ПБ":
                if re.match(r"^0\(М\d+\)$", op):
                    ret = True
                else:
                    jump = True
                    m = re.match(r"^L?(\d+)$", op)
                    if m and 2 * int(m.group(1)) < off:
                        back = True
        feats[off] = (calls, commons, locs, ret, jump, back, count)

    names, used = {}, set()
    # сперва ручные имена
    for word, nm in sorted(manual.items()):
        if word * 2 in labels:
            names[word] = nm
            used.add(nm)
    # затем автоматические
    for off in known:
        word = off // 2
        if word in names:
            continue
        # константы и переменные модуля (вне раздела команд) уже имеют
        # осмысленные имена в разборе БЕМШ (К<номер>, V<номер>) - берём их
        if off >= 2 * cmdwords and labels[off][:1] in "КV":
            names[word] = labels[off]
            used.add(labels[off])
            continue
        calls, commons, locs, ret, jump, back, count = feats[off]
        half = byoff.get(off)
        instr = ""
        if half is not None:
            instr = (decode(half)["name"] or "").upper()
        if calls:
            base = "ВЫЗОВ_" + sanitize(calls[0])
        elif commons:
            base = "БЛОК_" + sanitize(commons[0])
        elif locs:
            base = "ПЕР_" + locs[0]
        elif ret:
            base = "ВОЗВРАТ"
        elif back:
            # цель обратного перехода - начало цикла
            base = "ЦИКЛ_" + role_of(instr).replace(" ", "_")
        elif jump and count <= 2:
            # блок состоит из одного перехода - называем по его смыслу
            base = "ПЕРЕХОД"
        else:
            base = role_of(instr)
        nm = unique(base, used)
        used.add(nm)
        names[word] = nm
    return names


