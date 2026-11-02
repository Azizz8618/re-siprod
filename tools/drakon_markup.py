#!/usr/bin/env python3
"""Эталонный генератор разметки СИПРОДа для схем ДРАКОН.

Это спецификация того, что должен выдавать модуль-редактор (drakon/drakon.be):
разбор текста ДРАКОН -> компоновка схемы -> разметка *RED для печати.

Использование:
    python3 tools/drakon_markup.py ФАЙЛ.drakon > разметка.txt
    python3 tools/drakon_markup.py ФАЙЛ.drakon | tests/siprod/run.sh -   # печать
"""
from __future__ import annotations

import re
import sys

# ---------------------------------------------------------------- иконки ---
# Каждая иконка: рамка и подпись. Ширина подбирается по тексту.
ACTION, BRANCH, ADDRESS, END, HEADER, QUESTION, CHOICE, VARIANT = (
    "action", "branch", "address", "end", "header", "question", "choice", "variant")

INNER = 20          # минимальная ширина поля текста
GAP_COL = 4         # зазор между основной вертикалью и правым плечом
GAP_ROW = 2         # зазор по вертикали


class Icon:
    """Иконка схемы: вид, текст, координаты."""

    def __init__(self, kind, text="", width=None):
        self.kind = kind
        self.text = text
        self.x = 0            # левый край
        self.y = 0            # верх
        self.w = 0            # ширина рамки
        self.h = 0            # высота рамки
        self.lines = []        # рисуемые строки

    # -- геометрия ---------------------------------------------------------
    def wrap(self, width):
        """Разбить текст на строки шириной width."""
        out = []
        for para in self.text.split("\n"):
            words, cur = para.split(), ""
            for w in words:
                cand = (cur + " " + w).strip()
                if len(cand) <= width or not cur:
                    cur = cand
                else:
                    out.append(cur)
                    cur = w
            out.append(cur)
        return out or [""]

    def build(self):
        """Построить рисунок иконы (строки) и вычислить размеры.

        В GOST-10859 нет обратной косой черты, поэтому скосы рисуются
        символом "/" с обеих сторон.
        """
        k = self.kind
        if k == BRANCH:
            # трапеция: верхний край короче нижнего на 2
            width = max(INNER, max(len(l) for l in self.wrap(INNER)))
            body = self.wrap(width)
            w = width + 4
            lines = ["  " + "+" + "-" * (w - 4) + "+"]
            for t in body:
                lines.append(" /" + t.center(w - 3) + "/")
            lines.append("+" + "-" * (w - 2) + "+")
        elif k == ADDRESS:
            # трапеция: верхний край уже, низ шире
            width = max(INNER, max(len(l) for l in self.wrap(INNER)))
            body = self.wrap(width)
            w = width + 4
            lines = ["   " + "+" + "-" * (w - 6) + "+"]
            for t in body:
                lines.append("  /" + t.center(w - 3) + "/")
            lines.append(" " + "+" + "-" * (w - 4) + "+")
        elif k == END:
            t = self.text or "конец"
            w = max(10, len(t) + 6)
            lines = ["." + "-" * (w - 2) + ".",
                     "(" + t.center(w - 2) + ")",
                     "+" + "-" * (w - 2) + "+"]
        elif k == HEADER:
            width = max(INNER, max(len(l) for l in self.wrap(INNER)))
            body = self.wrap(width)
            w = width + 2
            lines = ["." + "-" * (w - 2) + "."]
            for t in body:
                lines.append("(" + t.center(width) + ")")
            lines.append("+" + "-" * (w - 2) + "+")
        elif k == QUESTION:
            # шестиугольник: текст между косыми линиями
            width = max(INNER, max(len(l) for l in self.wrap(INNER)))
            body = self.wrap(width)
            w = width + 6
            lines = ["  " + "+" + "-" * (w - 4) + "+"]
            for i, t in enumerate(body):
                if i:
                    lines.append("|" + t.center(w - 2) + "|")
                else:
                    lines.append("<" + t.center(w - 2) + ">")
            lines.append(" /" + " " * (w - 3) + "/")
            lines.append("  " + "+" + "-" * (w - 4) + "+")
        elif k == CHOICE:
            width = max(INNER, max(len(l) for l in self.wrap(INNER)))
            body = self.wrap(width)
            w = width + 6
            lines = ["  " + "+" + "-" * (w - 4) + "+"]
            for t in body:
                lines.append(" /" + t.center(w - 3) + "/")
            lines.append("+" + "-" * (w - 2) + "+")
        elif k == VARIANT:
            width = max(INNER, max(len(l) for l in self.wrap(INNER)))
            body = self.wrap(width)
            w = width + 2
            lines = ["+" + "-" * (w - 2) + "+"]
            for t in body:
                lines.append("|" + t.center(width) + "|")
            lines.append("+" + "-" * (w - 2) + "+")
        else:                                   # ACTION
            width = max(INNER, max(len(l) for l in self.wrap(INNER)))
            body = self.wrap(width)
            w = width + 2
            lines = ["+" + "-" * (w - 2) + "+"]
            for t in body:
                lines.append("|" + t.center(width) + "|")
            lines.append("+" + "-" * (w - 2) + "+")
        self.lines = lines
        self.w = w
        self.h = len(lines)
        return self


# ---------------------------------------------------------------- разбор ---
KEY = re.compile(r"^([А-ЯЁ]+)\s*:?\s*(.*)$")


class Node:
    """Узел дерева схемы."""

    def __init__(self, kind, text="", children=None):
        self.kind = kind
        self.text = text
        self.children = children or []
        self.icon = None
        self.col = 0        # колонка основной вертикали
        self.row = 0        # строка верха иконы
        self.branches = None    # правые плечи: (ось, первая икона, низ)
        self.main_bottom = None # первая свободная строка под основным путём
        self.next_node = None   # следующая икона цепочки (вертикальная линия)


def side_branches(node):
    """Правые плечи развилки: список списков узлов.

    ИНАЧЕ даёт только потомков, ВАРИАНТ - свою икону плюс потомков.
    """
    branches = []
    for child in node.children:
        if child.kind == "ИНАЧЕ" and child.children:
            branches.append(child.children)
        elif child.kind == "ВАРИАНТ" and (child.text or child.children):
            branches.append([child] + child.children)
    return branches


def parse(text):
    """Текст ДРАКОН -> дерево узлов (вложенность по отступам).

    Строки, начинающиеся с `*`, - комментарии, пропускаются.
    """
    items = []
    for l in text.splitlines():
        if not l.strip():
            continue
        if l.lstrip().startswith("*"):
            continue
        items.append((len(l) - len(l.lstrip()), l.strip()))
    if not items:
        raise ValueError("пустая схема: нет ни одной иконы")
    pos = [0]

    def block(ind):
        out = []
        while pos[0] < len(items):
            i, s = items[pos[0]]
            if i < ind:
                break
            pos[0] += 1
            m = KEY.match(s)
            word = m.group(1) if m else s
            rest = m.group(2).strip() if m else ""
            if word in ("ТО", "ИНАЧЕ", "ВАРИАНТ"):
                out.append(Node(word, rest, block(i + 1)))
                continue
            node = Node(word, rest)
            if word in ("ЕСЛИ", "ВЫБОР", "ЦИКЛ"):
                node.children = block(i + 1)
            out.append(node)
        return out

    return block(0)


# ------------------------------------------------------------ компоновка ---
def make_icon(node):
    """Вид иконы по ключевому слову."""
    k = node.kind
    if k == "ЗАГОЛОВОК":
        return Icon(HEADER, node.text).build()
    if k == "ВЕТКА":
        return Icon(BRANCH, node.text).build()
    if k == "АДРЕС":
        return Icon(ADDRESS, node.text).build()
    if k == "КОНЕЦ":
        return Icon(END, node.text or "конец").build()
    if k == "ЕСЛИ" or k == "ЦИКЛ":
        return Icon(QUESTION, node.text).build()
    if k == "ВЫБОР":
        return Icon(CHOICE, node.text).build()
    if k == "ВАРИАНТ":
        return Icon(VARIANT, node.text).build()
    return Icon(ACTION, node.text).build()


def layout(nodes, col, row, out, align="center", tail=None):
    """Разложить узлы вертикально; вернуть (следующая строка, ось, хвост).

    Иконы цепочки центрируются по колонке col (шампур); попутно
    заполняются связи next_node - вертикальные линии между иконами.
    tail - узел, к которому привязывается первая икона цепочки (хвост
    вызывающей цепочки).  Возвращаемый хвост - последний узел этой
    цепочки (для связи с далее идущими иконами вызывающей цепочки).
    """
    y = row
    maxx = col
    for node in nodes:
        icon = make_icon(node)
        node.icon = icon
        icon.x = col - icon.w // 2 if align == "center" else col
        icon.y = y
        if tail is not None:
            tail.next_node = node
        out.append(node)
        y += icon.h + GAP_ROW
        main_kids = []
        if node.kind == "ЦИКЛ":
            main_kids = node.children      # тело цикла - сами потомки
        else:
            for child in node.children:
                if child.kind == "ТО":
                    main_kids = child.children
        branches = side_branches(node)
        subtree_tail = node
        if main_kids:
            y2, mx, tail2 = layout(main_kids, col, y, out, tail=node)
            y = max(y, y2)
            maxx = max(maxx, mx)
            subtree_tail = tail2
            node.main_bottom = y2 - GAP_ROW
        else:
            node.main_bottom = icon.y + icon.h
        if branches:
            row0 = icon.y + icon.h - 2       # строка выхода вправо
            rx = col + icon.w // 2 + GAP_COL
            ry = max(node.icon.y + node.icon.h // 2 + 1, row0 + 1)
            node.branches = []
            for kids in branches:
                # у плеча своя ось: иконы центрируются на колонке оси
                wmax = max(make_icon(k).w for k in kids)
                rail = rx + wmax // 2
                yb, _, _t = layout(kids, rail, ry, out)
                node.branches.append((rail, kids[0].icon, yb - GAP_ROW))
                maxx = max(maxx, rail + wmax - wmax // 2)
                rx = rail + (wmax - wmax // 2) + GAP_COL
            # плечи удлиняют конструкцию: следующая икона основной
            # колонки - ниже всех плеч
            y = max(y, max(b[2] for b in node.branches) + GAP_ROW)
        tail = subtree_tail
    return y, maxx, tail


def render(nodes):
    """Дерево -> строки схемы.

    Вертикаль основной колонки идёт МЕЖДУ иконами (сверху до верха
    следующей), как в ДРАКОН: линия подходит к рамке, а не проходит
    сквозь неё.
    """
    flat = []
    layout(nodes, 0, 0, flat)
    rows = 0
    for node in flat:
        rows = max(rows, node.icon.y + node.icon.h)
    canvas = [[] for _ in range(rows)]

    def put(x, y, ch):
        r, c = y, x
        if r < 0 or r >= len(canvas):
            return
        while len(canvas[r]) <= c:
            canvas[r].append(" ")
        canvas[r][c] = ch

    xmin = min(n.icon.x for n in flat)
    for node in flat:
        icon = node.icon
        icon.x -= xmin
        for i, l in enumerate(icon.lines):
            for j, ch in enumerate(l):
                put(icon.x + j, icon.y + i, ch)

    # соединительные линии: из низа иконы в верх следующей (та же колонка)
    for a in flat:
        if not a.next_node:
            continue
        ia, ib = a.icon, a.next_node.icon
        col = ia.x + ia.w // 2
        for r in range(ia.y + ia.h, ib.y):
            put(col, r, "|")

    # шина выхода вправо: от иконы вопроса/выбора к осям правых плеч
    for node in flat:
        icon = node.icon
        if not node.branches:
            continue
        col = icon.x + icon.w // 2
        row0 = icon.y + icon.h - 2
        last_rail = max(b[0] for b in node.branches)
        for x in range(icon.x + icon.w, last_rail):
            put(x, row0, "-")
        for rail, first, _bottom in node.branches:
            put(rail, row0, "+")
            for r in range(row0 + 1, first.y):
                put(rail, r, "|")

    # возврат правых плеч на основную вертикаль (слияние маршрутов)
    for node in flat:
        icon = node.icon
        if not node.branches:
            continue
        col = icon.x + icon.w // 2
        base = max([node.main_bottom] + [b[2] for b in node.branches])
        nxt = [n.icon.y for n in flat
               if n is not node
               and n.icon.x + n.icon.w // 2 == col
               and n.icon.y >= base]
        if nxt and min(nxt) <= base:
            continue          # правее некуда: плечо ниже следующей иконы
        merge_row = base
        rails = [b[0] for b in node.branches]
        for rail, _first, bottom in node.branches:
            for r in range(bottom, merge_row):
                put(rail, r, "|")
        for x in range(col + 1, max(rails)):
            put(x, merge_row, "-")
        for rail in rails:
            put(rail, merge_row, "+")
        put(col, merge_row, "+")

    out = []
    for r in canvas:
        out.append("".join(r).rstrip())
    while out and not out[-1]:
        out.pop()
    return out


def markup(nodes):
    """Дерево -> текст разметки СИПРОДа (*RED)."""
    art = render(nodes)
    out = ["*RED", "*RG*RU"]
    for l in art:
        # карта не длиннее 80 символов: "*/*D"+76 или "*D"+78
        first = True
        while l or first:
            take = 76 if first else 78
            chunk, l = l[:take], l[take:]
            out.append(("*/*D" if first else "*D") + chunk)
            first = False
    out.append("*E")
    out.append("*END")
    return "\n".join(out) + "\n"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    src = open(sys.argv[1], encoding="utf-8").read()
    try:
        nodes = parse(src)
    except ValueError as e:
        print("drakon_markup: %s" % e, file=sys.stderr)
        return 2
    sys.stdout.write(markup(nodes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
