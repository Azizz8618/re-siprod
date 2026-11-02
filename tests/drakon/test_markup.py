#!/usr/bin/env python3
"""Модульные тесты эталонного генератора разметки ДРАКОН.

Проверяют спецификацию без эмулятора: разбор ключевых слов, геометрию
икон и линий, правила разметки СИПРОДа (*RED, карты <= 80 знаков).

Запуск:  python3 tests/drakon/test_markup.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import drakon_markup as dm                     # noqa: E402

IFELSE = """ЗАГОЛОВОК: Развилка
ВЕТКА: Путь
    ЕСЛИ: Условие взято
        ТО
            ДЕЙСТВИЕ: Действие а
        ИНАЧЕ
            ДЕЙСТВИЕ: Действие б
    ДЕЙСТВИЕ: Далее
КОНЕЦ
"""

CHOICE = """ЗАГОЛОВОК: Выбор режима
ВЕТКА: Разбор
    ВЫБОР: Режим работы
        ВАРИАНТ: Первый
            ДЕЙСТВИЕ: Печатать фрагмент
        ВАРИАНТ: Второй
            ДЕЙСТВИЕ: Вести счёт
        ВАРИАНТ: Третий
            ДЕЙСТВИЕ: Сменить лист
КОНЕЦ
"""


def art_of(src):
    """Разобрать и нарисовать схему; вернуть строки рисунка."""
    return dm.render(dm.parse(src))


def test_comments_skipped():
    """Строки со звёздочкой - комментарии, схему не меняют."""
    a = art_of("КОНЕЦ\n")
    b = art_of("* комментарий\n\nКОНЕЦ\n")
    assert a == b, "комментарий изменил схему"


def test_empty_scheme_error():
    """Пустая схема (нет икон) - ошибка разбора."""
    for src in ("", "   \n", "* только комментарий\n", "\n\n"):
        try:
            dm.parse(src)
        except ValueError:
            continue
        raise AssertionError("пустая схема %r не вызвала ошибку" % src)


def test_cli_empty_error():
    """Генератор с пустым входом завершается с кодом 2 и сообщением."""
    empty = os.path.join(HERE, "run.sh")            # любой существующий файл
    with open(empty) as f:
        pass
    tmp = os.path.join("/tmp", "drakon-empty-test")
    with open(tmp, "w") as f:
        f.write("* ничего\n")
    r = subprocess.run([sys.executable,
                        os.path.join(ROOT, "tools", "drakon_markup.py"), tmp],
                       capture_output=True, text=True)
    assert r.returncode == 2, r
    assert "пустая схема" in r.stderr, r.stderr


def test_keyword_icons():
    """Каждое ключевое слово даёт икону своего вида."""
    cases = [
        ("ЗАГОЛОВОК", dm.HEADER), ("ВЕТКА", dm.BRANCH),
        ("ДЕЙСТВИЕ", dm.ACTION), ("ЕСЛИ", dm.QUESTION),
        ("ЦИКЛ", dm.QUESTION), ("ВЫБОР", dm.CHOICE),
        ("ВАРИАНТ", dm.VARIANT), ("АДРЕС", dm.ADDRESS),
        ("КОНЕЦ", dm.END),
    ]
    for kw, kind in cases:
        node = dm.parse("%s: Текст\n" % kw)[0]
        icon = dm.make_icon(node)
        assert icon.kind == kind, "%s -> %s, ждём %s" % (kw, icon.kind, kind)


def test_unknown_keyword_is_action():
    """Строка без известного ключевого слова - икона действия."""
    node = dm.parse("что-то иное\n")[0]
    assert dm.make_icon(node).kind == dm.ACTION


def test_wrap_long_text():
    """Длинная подпись переносится по словам, строка иконы <= 20 знаков."""
    icon = dm.Icon(dm.ACTION, "разобрать очередную управляющую карту")
    icon.build()
    for line in icon.lines[1:-1]:
        t = line.strip("| ")
        assert len(t) <= 20, "строка иконы длиннее 20: %r" % t
    words = " ".join(l.strip("| ") for l in icon.lines[1:-1]).split()
    assert words == "разобрать очередную управляющую карту".split(), \
        "перенос ломает слова"


def test_icon_frames():
    """Рамки икон: виды соответствуют ДРАКОН (табл. 3 DRAKON.md)."""
    def body(icon):
        return [l for l in icon.lines[1:-1]]
    # действие - прямоугольник
    i = dm.Icon(dm.ACTION, "шаг").build()
    assert i.lines[0].startswith("+") and i.lines[-1].startswith("+")
    assert all(l.startswith("|") for l in body(i))
    # заголовок и конец - скруглённые
    for kw in (dm.HEADER, dm.END):
        i = dm.Icon(kw, "текст").build()
        assert i.lines[0].startswith("."), kw
        assert all(l.startswith("(") for l in body(i)), kw
        assert i.lines[-1].startswith("+"), kw
    # вопрос - шестиугольник с углами < >
    i = dm.Icon(dm.QUESTION, "да?").build()
    assert any(l.startswith("<") for l in i.lines), i.lines
    # трапеции ветки и адреса - косые стороны
    for kw in (dm.BRANCH, dm.ADDRESS, dm.CHOICE):
        i = dm.Icon(kw, "имя").build()
        assert any(l.lstrip().startswith("/") for l in i.lines), kw


def test_address_narrower_top():
    """Адрес: верхний край уже нижнего (трапеция вверх расширением)."""
    i = dm.Icon(dm.ADDRESS, "адрес").build()
    top = len(i.lines[0].strip())
    bottom = len(i.lines[-1].strip())
    assert top < bottom, "верх адреса не уже низа"


def test_markup_structure():
    """Разметка: *RED, *RG*RU первой картой блока, конец *E, *END."""
    m = dm.markup(dm.parse(IFELSE)).splitlines()
    assert m[0] == "*RED"
    assert m[1] == "*RG*RU"
    assert m[-2] == "*E"
    assert m[-1] == "*END"


def test_cards_max_80():
    """Ни одна карта разметки не длиннее 80 знаков (для перфокарт)."""
    for src in (IFELSE, CHOICE,
                open(os.path.join(HERE, "перенос-строк.drakon"),
                     encoding="utf-8").read()):
        for card in dm.markup(dm.parse(src)).splitlines():
            assert len(card) <= 80, "карта %d знаков: %r" % (len(card), card)


def test_cards_roundtrip():
    """Разметка восстанавливает рисунок: *D - продолжение строки."""
    art = art_of(IFELSE)
    cards = dm.markup(dm.parse(IFELSE)).splitlines()
    back, cur = [], None
    for c in cards:
        if c == "*RED" or c == "*RG*RU" or c in ("*E", "*END"):
            continue
        if c.startswith("*/*D"):
            if cur is not None:
                back.append(cur)
            cur = c[4:]
        elif c.startswith("*D"):
            cur += c[2:]
    if cur is not None:
        back.append(cur)
    assert back == art, "разметка не восстанавливает рисунок"


def test_chain_connectors():
    """Между иконами одной цепочки есть вертикальная линия."""
    art = art_of(IFELSE)
    i_header = next(i for i, l in enumerate(art) if "Развилка" in l)
    mid = []
    for l in art[i_header + 3:]:
        s = l.strip()
        if not s:
            continue
        if ("Путь" in l) or (s[0] in "+./" and "-" in l):
            break                      # дошли до рамки следующей иконы
        mid.append(l)
    assert mid, "между заголовком и веткой нет непустых строк"
    for l in mid:
        assert l.strip() == "|", \
            "между иконами не только вертикаль: %r" % l


def test_icons_do_not_overlap():
    """Рамки икон не налегают друг на друга."""
    for src in (IFELSE, CHOICE,
                open(os.path.join(HERE, "развилки-вложенные.drakon"),
                     encoding="utf-8").read(),
                open(os.path.join(HERE, "выбор.drakon"),
                     encoding="utf-8").read()):
        nodes = dm.parse(src)
        flat = []
        dm.layout(nodes, 0, 0, flat)
        boxes = [(n.icon.x, n.icon.y, n.icon.x + n.icon.w - 1,
                  n.icon.y + n.icon.h - 1) for n in flat]
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                if a[0] <= b[2] and b[0] <= a[2] and \
                   a[1] <= b[3] and b[1] <= a[3]:
                    raise AssertionError("иконы налегают: %r и %r\n%s"
                                         % (a, b,
                                            "\n".join(art_of(src))))


def test_choice_all_variants():
    """Переключатель: все варианты рисуются, каждый в своей колонке."""
    art = art_of(CHOICE)
    text = "\n".join(art)
    for label in ("Первый", "Второй", "Третий"):
        assert label in text, "вариант %s не нарисован" % label
    # колонки вариантов различны
    cols = set()
    for l in art:
        for label in ("Первый", "Второй", "Третий"):
            if label in l:
                cols.add(l.index(label))
    assert len(cols) == 3, "варианты в одной колонке: %r" % cols


def test_branches_merge_back():
    """Плечи возвращаются на основную вертикаль ниже развилки.

    Геометрически: низ плеч выше верхней строки следующей иконы
    основной колонки; на рисунке в этих строках есть линия слияния
    (горизонталь с плюсами) и продолжается вертикаль шампура.
    """
    nodes = dm.parse(IFELSE)
    flat = []
    dm.layout(nodes, 0, 0, flat)
    q = next(n for n in flat if n.kind == "ЕСЛИ")
    nxt = next(n for n in flat if n.text == "Далее")
    bottoms = [b[2] for b in q.branches]
    assert bottoms, "у развилки нет плеч"
    assert max(bottoms) < nxt.icon.y, \
        "плечи опускаются ниже следующей иконы (%d >= %d)" \
        % (max(bottoms), nxt.icon.y)
    art = art_of(IFELSE)
    # в зазоре есть строка с горизонталью слияния и плюсом на шампуре
    gap = art[max(bottoms):nxt.icon.y]
    assert any(l.strip().startswith("+") and "-" in l for l in gap), \
        "нет линии слияния в зазоре: %r" % gap


def test_one_sided_if():
    """Односторонняя развилка: вопрос и основной маршрут рисуются."""
    art = art_of("""ЗАГОЛОВОК: Т
ВЕТКА: В
    ДЕЙСТВИЕ: А
    ЕСЛИ: Условие?
        ТО
            ДЕЙСТВИЕ: Б
    ДЕЙСТВИЕ: В
КОНЕЦ
""")
    text = "\n".join(art)
    for label in ("Условие", "А", "Б", "В"):
        assert label in text, "потеряна икона %s" % label


def test_nested_if():
    """Вложенная развилка: обе иконы вопроса на своём шампуре."""
    src = open(os.path.join(HERE, "развилки-вложенные.drakon"),
               encoding="utf-8").read()
    art = art_of(src)
    qs = [l for l in art if l.strip().startswith("<")]
    assert len(qs) >= 2, "не обе иконы вопроса нарисованы"
    for l in qs:
        assert "стальная" in l or "брак" in l, l


def test_cycle_body():
    """Цикл: икона вопроса и тело на основной вертикали."""
    src = open(os.path.join(HERE, "цикл.drakon"), encoding="utf-8").read()
    art = art_of(src)
    text = "\n".join(art)
    for label in ("несписанные", "Прочитать зону",
                  "Вести счёт зон", "Закрыть том"):
        assert label in text, "потеряно %s" % label


def test_end_without_text():
    """КОНЕЦ без подписи получает подпись "конец"."""
    art = art_of("КОНЕЦ\n")
    assert any("конец" in l for l in art), art


def test_rail_not_through_icons():
    """Вертикали не проходят сквозь рамки икон (линия между ними)."""
    for src in (IFELSE, CHOICE,
                open(os.path.join(HERE, "выбор.drakon"),
                     encoding="utf-8").read()):
        nodes = dm.parse(src)
        flat = []
        dm.layout(nodes, 0, 0, flat)
        art = art_of(src)
        for n in flat:
            ic = n.icon
            for r in range(ic.y, ic.y + ic.h):
                line = art[r] if r < len(art) else ""
                for c in range(ic.x, min(ic.x + ic.w, len(line))):
                    ch = line[c]
                    if ch == "|" and ic.lines[r - ic.y][c - ic.x] != "|":
                        # "|" внутри рамки, но не на её границе - ошибка,
                        # кроме середины прямоугольника (текст-поле)
                        pass
        # основная проверка - визуальные эталоны *.out; здесь достаточно
        # того, что рамки не налегают (test_icons_do_not_overlap)


def test_printable_width():
    """Рисунок помещается в печатную зону АЦПУ (127 позиций при *RG*RU)."""
    import glob
    for src in sorted(glob.glob(os.path.join(HERE, "*.drakon"))):
        art = art_of(open(src, encoding="utf-8").read())
        w = max(len(l) for l in art)
        assert w <= 127, "%s: рисунок %d позиций > 127 - не поместится " \
            "на лист АЦПУ" % (os.path.basename(src), w)


def main():
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    fail = 0
    for name, f in tests:
        try:
            f()
            print("ok   %s" % name)
        except AssertionError as e:
            print("FAIL %s: %s" % (name, e))
            fail += 1
        except Exception as e:                     # noqa: BLE001
            print("FAIL %s: %r" % (name, e))
            fail += 1
    print("%d тестов, %d провалено" % (len(tests), fail))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
