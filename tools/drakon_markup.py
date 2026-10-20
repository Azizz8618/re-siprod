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
        self.right = []     # (икона, узел) - правое плечо


def parse(text):
    """Текст ДРАКОН -> дерево узлов (вложенность по отступам)."""
    items = []
    for l in text.splitlines():
        if not l.strip():
            continue
        items.append((len(l) - len(l.lstrip()), l.strip()))
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
    if k == "ЕСЛИ":
        return Icon(QUESTION, node.text).build()
    if k == "ВЫБОР":
        return Icon(CHOICE, node.text).build()
    if k == "ВАРИАНТ":
        return Icon(VARIANT, node.text).build()
    return Icon(ACTION, node.text).build()


def layout(nodes, col, row, out, align="center"):
    """Разложить узлы вертикально; вернуть (следующая строка, правый край).

    align="center" - иконы центрируются по колонке (основная вертикаль);
    align="left"   - по левому краю (правые плечи).
    """
    y = row
    maxx = col
    for node in nodes:
        icon = make_icon(node)
        node.icon = icon
        icon.x = col - icon.w // 2 if align == "center" else col
        icon.y = y
        out.append(node)
        y += icon.h + GAP_ROW
        main_kids, side_kids = [], []
        for child in node.children:
            if child.kind == "ИНАЧЕ" or child.kind == "ВАРИАНТ":
                side_kids = child.children
            else:
                main_kids = child.children
        if main_kids:
            y2, mx = layout(main_kids, col, y, out)
            y = max(y, y2)
            maxx = max(maxx, mx)
        if side_kids:
            rx = col + icon.w // 2 + GAP_COL
            ry = node.icon.y + node.icon.h // 2 + 1
            _, mx = layout(side_kids, rx, ry, out, align="left")
            maxx = max(maxx, mx)
    return y, maxx


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
    for a, b in zip(flat, flat[1:]):
        ia, ib = a.icon, b.icon
        if ia.x != ib.x:
            continue
        col = ia.x + ia.w // 2
        for r in range(ia.y + ia.h, ib.y):
            put(col, r, "|")

    # горизонтальный выход из иконы вопроса в правое плечо
    for node in flat:
        icon = node.icon
        side = [c for c in node.children if c.kind in ("ИНАЧЕ", "ВАРИАНТ")]
        if not side:
            continue
        col = icon.x + icon.w // 2
        row = icon.y + icon.h - 2
        for child in side:
            if not child.children:
                continue
            sub = child.children[0].icon
            for x in range(col + 1, sub.x):
                put(x, row, "-")
            put(sub.x, row, "+")

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
        # карта не длиннее 80 символов: длинные строки режем
        first = True
        while l or first:
            chunk, l = l[:77], l[77:]
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
    nodes = parse(src)
    sys.stdout.write(markup(nodes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
