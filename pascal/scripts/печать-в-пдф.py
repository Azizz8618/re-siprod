#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""печать-в-пдф.py - печать АЦПУ (выдача задач БЭСМ-6/СИПРОД) в PDF.

Сценарий, проверенный на задании «План внедрения блочного шифрования»
(12.11.2026): страница PDF = лист печати; листы делятся по форм-фидам
(\x0c), как их выдаёт экстракод 64 (прогон страницы) в журнале dispak.

Параметры печати (зафиксированы сценарием СИПРОД -> PDF):
  - шрифт DejaVu Sans Mono; размер выводится из сетки: кегль подобран
    так, чтобы литера занимала ровно 6 pt ширины (сетка АЦПУ
    6 pt/колонку) - получается 9.97 pt;
  - 128 колонок (полный лист АЦПУ БЭСМ-6), до 70 строк на листе;
  - межстрочный интервал 9.3 pt (между базовыми линиями);
  - пустые листы (после снятия краевых пустых строк) не печатаются.

usage: печать-в-пдф.py <печать.txt> [<выход.pdf>]
  без второго аргумента выход - <печать>.pdf рядом со входом.

Переменные окружения (необязательные):
  DEJAVU_MONO - путь к DejaVuSansMono.ttf (по умолчанию - стандартный
  путь Debian/Ubuntu и альтернативные места, см. ниже).
"""
import os
import sys

from reportlab.lib.pagesizes import landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

# ---- параметры печати (сценарий СИПРОД -> PDF) ----
COL = 6.0      # pt на колонку АЦПУ (сетка)
LEAD = 9.3     # pt между базовыми линиями строк
MARGIN = 28.0  # поля листа PDF, pt
MAXCOLS = 128  # колонок АЦПУ на листе
MAXLINES = 70  # строк АЦПУ на листе

FONT_NAME = 'DejaVuMono'


def найти_шрифт():
    env = os.environ.get('DEJAVU_MONO')
    if env:
        return env
    candidates = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
        '/usr/share/fonts/dejavu/DejaVuSansMono.ttf',
        '/usr/share/fonts/TTF/DejaVuSansMono.ttf',
        '/usr/local/share/fonts/DejaVuSansMono.ttf',
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    raise SystemExit('СТОП: не найден DejaVuSansMono.ttf; '
                     'задайте переменную DEJAVU_MONO')


def страницы(путь):
    """Печать -> список листов: деление по форм-фидам, краевые пустые
    строки сняты, пустые листы выброшены."""
    lines = open(путь, encoding='utf-8').read().split('\n')
    chunks, cur = [], []
    for l in lines:
        if '\x0c' in l:
            parts = l.split('\x0c')
            for k, p in enumerate(parts):
                if k > 0:
                    chunks.append(cur)
                    cur = []
                cur.append(p)
        else:
            cur.append(l)
    chunks.append(cur)
    pages = []
    for c in chunks:
        while c and not c[0].strip():
            c.pop(0)
        while c and not c[-1].strip():
            c.pop()
        if c:
            pages.append(c)
    return pages


def main():
    if len(sys.argv) not in (2, 3):
        raise SystemExit(__doc__)
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) == 3 else \
        os.path.splitext(src)[0] + '.pdf'

    pdfmetrics.registerFont(TTFont(FONT_NAME, найти_шрифт()))
    # кегль из сетки: ширина литеры = COL
    adv = pdfmetrics.stringWidth('N', FONT_NAME, 1000) / 1000.0
    size = COL / adv
    asc = pdfmetrics.getAscent(FONT_NAME) / 1000.0 * size
    desc = abs(pdfmetrics.getDescent(FONT_NAME)) / 1000.0 * size

    W = MAXCOLS * COL + 2 * MARGIN
    H = asc + desc + (MAXLINES - 1) * LEAD + 2 * MARGIN

    pages = страницы(src)
    c = canvas.Canvas(dst, pagesize=(W, H))
    c.setTitle('БЭСМ-6. Печать АЦПУ (задача ДИСПАК)')
    c.setAuthor('СИПРОД')
    base_y = H - MARGIN - asc
    for pg in pages:
        if len(pg) > MAXLINES:
            print('предупреждение: лист с %d строками (>%d), '
                  'хвост уйдёт за лист' % (len(pg), MAXLINES))
        y = base_y
        c.setFont(FONT_NAME, size)
        for l in pg:
            c.drawString(MARGIN, y, l[:MAXCOLS])
            y -= LEAD
        c.showPage()
    c.save()
    print('листов печати: %d; страниц PDF: %d -> %s'
          % (len(pages), len(pages), dst))


if __name__ == '__main__':
    main()
