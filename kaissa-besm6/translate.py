#!/usr/bin/env python3
"""
Транслятор машинного кода М-20 -> БЭСМ-6 (символьный формат .b6 для simh).

Схема адресации: адрес БЭСМ-6 = адрес М-20 * 8.
Каждая команда М-20 занимает блок из 8 ячеек БЭСМ-6 (7 команд + 1 NOP).
Данные М-20 занимают 1 ячейку по адресу М-20 * 8.

Эмуляция регистров:
  ACC   -> РР
  M[1]  -> РА (регистр адреса М-20)
  M[2]  -> Ω (0/1)
  M[3]  -> РМР
  M[4]  -> временный T
  M[5]  -> временный T2
"""

import sys
import re
from collections import Counter

M20_OPS = [
    "п",   "с",   "в",   "ва",  "д",   "у",   "спа", "цс",
    "вв",  "пем", "пм",  "см",  "сдма", "н",   "пв",  "дпа",
    "пкл", "со",  "во",  "вао", "до",  "уо",  "спп", "цв",
    "ввк", "пен", "пн",  "вм",  "сдмп", "нс",  "пе",  "дпб",
    "пмс", "сн",  "вн",  "ван", "к",   "ун",  "впа", "мрп",
    "ма",  "пум", "ра",  "ск",  "сдса", "и",   "пб",  "ирп",
    "пнс", "сон", "вон", "ваон","ко",  "уон", "впп", "цсд",
    "мб",  "пун", "рс",  "вк",  "сдсп", "или", "пу",  "стоп",
]

R_RA = 1
R_OM = 2
R_RMR = 3
R_T = 4
R_T2 = 5

T_OMEGA = 0o7770 * 8
T_TMP = 0o7771 * 8

class Word:
    def __init__(self, addr, value):
        self.addr = addr
        self.value = value
        self.flags = (value >> 42) & 7
        self.op = (value >> 36) & 0o77
        self.a1 = (value >> 24) & 0o7777
        self.a2 = (value >> 12) & 0o7777
        self.a3 = value & 0o7777
        self.mnem = M20_OPS[self.op] if self.op < 64 else "?"

    def is_code(self):
        exp = (self.value >> 37) & 0o77
        tag = (self.value >> 44) & 1
        return (self.op <= 0o77) and not (tag == 1 and exp != 0)

def load_m20(filename):
    mem = {}
    addr = 0
    start = 0o5000
    with open(filename, 'rb') as f:
        data = f.read()
        if data.startswith(b'\xef\xbb\xbf'):
            data = data[3:]
        text = data.decode('utf-8', errors='replace')
    for line in text.splitlines():
        line = line.split(';')[0].strip()
        if not line:
            continue
        if line.startswith(':'):
            addr = int(line[1:], 8)
        elif line.startswith('@'):
            start = int(line[1:], 8)
        elif line.startswith('='):
            pass
        elif line[0] in '01234567':
            digits = re.sub(r'[^0-7]', '', line)
            if len(digits) >= 15:
                word = int(digits[:15], 8)
                mem[addr] = Word(addr, word)
                addr += 1
    return mem, start

def b6a(m20addr):
    """Адрес БЭСМ-6 для адреса М-20."""
    return m20addr * 8

def emit(op, addr=0, reg=0):
    s = op
    if addr:
        if addr >= 0o77700:
            s += f" -{0o100000 - addr:o}"
        else:
            s += f" {addr:o}"
    if reg:
        s += f"({reg:o})"
    return s

def translate_word(w):
    """
    Трансляция одной команды М-20 в список команд БЭСМ-6.
    Каждая команда = строка, адрес = b6a(адрес М-20) + смещение.
    """
    out = []
    a1, a2, a3 = w.a1, w.a2, w.a3
    op = w.op
    mod1 = R_RA if (w.flags & 4) else 0
    mod2 = R_RA if (w.flags & 2) else 0
    mod3 = R_RA if (w.flags & 1) else 0

    # Адрес базовой ячейки для этой команды М-20
    base = b6a(w.addr)

    def emit_at(offset, op, addr=0, reg=0):
        """Эмитировать команду по смещению от base."""
        out.append((base + offset, emit(op, addr, reg)))

    # --- Логические ---
    if op == 0o00:  # п
        emit_at(0, "сч", b6a(a1), mod1)
        emit_at(1, "зп", b6a(a3), mod3)

    elif op == 0o15:  # со
        emit_at(0, "сч", b6a(a1), mod1)
        emit_at(1, "нтж", b6a(a2), mod2)
        emit_at(2, "зп", b6a(a3), mod3)
        emit_at(3, "по", base + 5)      # ACC==0 -> +2
        emit_at(4, "уиа", 1, R_OM)
        emit_at(5, "пб", base + 7)
        emit_at(6, "уиа", 0, R_OM)

    elif op == 0o35:  # сон
        emit_at(0, "сч", b6a(a1), mod1)
        emit_at(1, "нтж", b6a(a2), mod2)
        emit_at(2, "зп", b6a(a3), mod3)
        emit_at(3, "по", base + 5)
        emit_at(4, "уиа", 1, R_OM)
        emit_at(5, "пб", base + 7)
        emit_at(6, "уиа", 0, R_OM)
        emit_at(7, "пио", base + 10, R_OM)  # Ω==0 -> стоп
        emit_at(8, "пб", base + 11)
        emit_at(9, "стоп")
        emit_at(10, "сч")  # NOP
        emit_at(11, "сч")  # NOP

    elif op == 0o55:  # и
        emit_at(0, "сч", b6a(a1), mod1)
        emit_at(1, "и", b6a(a2), mod2)
        emit_at(2, "зп", b6a(a3), mod3)
        emit_at(3, "по", base + 5)
        emit_at(4, "уиа", 1, R_OM)
        emit_at(5, "пб", base + 7)
        emit_at(6, "уиа", 0, R_OM)

    elif op == 0o75:  # или
        emit_at(0, "сч", b6a(a1), mod1)
        emit_at(1, "или", b6a(a2), mod2)
        emit_at(2, "зп", b6a(a3), mod3)
        emit_at(3, "по", base + 5)
        emit_at(4, "уиа", 1, R_OM)
        emit_at(5, "пб", base + 7)
        emit_at(6, "уиа", 0, R_OM)

    # --- Адресная арифметика ---
    elif op == 0o13:  # см
        emit_at(0, "сч", b6a(a1), mod1)
        emit_at(1, "слц", b6a(a2), mod2)
        emit_at(2, "зп", b6a(a3), mod3)

    elif op == 0o33:  # вм
        emit_at(0, "сч", b6a(a1), mod1)
        emit_at(1, "вчоб", b6a(a2), mod2)
        emit_at(2, "зп", b6a(a3), mod3)

    elif op == 0o53:  # ск
        emit_at(0, "сч", b6a(a1), mod1)
        emit_at(1, "слц", b6a(a2), mod2)
        emit_at(2, "зп", b6a(a3), mod3)

    elif op == 0o73:  # вк
        emit_at(0, "сч", b6a(a1), mod1)
        emit_at(1, "вчоб", b6a(a2), mod2)
        emit_at(2, "зп", b6a(a3), mod3)

    # --- Сдвиги ---
    elif op in (0o14, 0o34, 0o54, 0o74):
        emit_at(0, "сч", b6a(a2), mod2)
        emit_at(1, "мод", T_TMP)
        emit_at(2, "зп", b6a(a3), mod3)
        emit_at(3, "по", base + 5)
        emit_at(4, "уиа", 1, R_OM)
        emit_at(5, "пб", base + 7)
        emit_at(6, "уиа", 0, R_OM)

    # --- Циклические ---
    elif op == 0o07:  # цс
        emit_at(0, "сч", b6a(a1), mod1)
        emit_at(1, "слц", b6a(a2), mod2)
        emit_at(2, "зп", b6a(a3), mod3)
        emit_at(3, "по", base + 5)
        emit_at(4, "уиа", 1, R_OM)
        emit_at(5, "пб", base + 7)
        emit_at(6, "уиа", 0, R_OM)

    elif op == 0o27:  # цв
        emit_at(0, "сч", b6a(a1), mod1)
        emit_at(1, "вчоб", b6a(a2), mod2)
        emit_at(2, "зп", b6a(a3), mod3)
        emit_at(3, "по", base + 5)
        emit_at(4, "уиа", 1, R_OM)
        emit_at(5, "пб", base + 7)
        emit_at(6, "уиа", 0, R_OM)

    elif op == 0o67:  # цсд
        emit_at(0, "сч", b6a(a1), mod1)
        emit_at(1, "мод", T_TMP)
        emit_at(2, "зп", b6a(a3), mod3)

    # --- Управление ---
    elif op == 0o16:  # пв
        emit_at(0, "сч", T_TMP, mod3)
        emit_at(1, "зп", b6a(a3), mod3)
        emit_at(2, "пв", b6a(a2), mod2)

    elif op == 0o36:  # пе
        emit_at(0, "сч", b6a(a1), mod1)
        emit_at(1, "зп", b6a(a3), mod3)
        emit_at(2, "пио", base + 5, R_OM)   # Ω==0 -> пропуск
        emit_at(3, "пб", b6a(a2), mod2)      # Ω==1 -> переход
        emit_at(4, "сч")  # NOP
        emit_at(5, "сч")  # NOP

    elif op == 0o56:  # пб
        emit_at(0, "сч", b6a(a1), mod1)
        emit_at(1, "зп", b6a(a3), mod3)
        emit_at(2, "пб", b6a(a2), mod2)

    elif op == 0o76:  # пу
        emit_at(0, "сч", b6a(a1), mod1)
        emit_at(1, "зп", b6a(a3), mod3)
        emit_at(2, "пио", base + 5, R_OM)   # Ω==0 -> пропуск
        emit_at(3, "пб", base + 6)           # Ω==1 -> пропуск
        emit_at(4, "сч")  # NOP
        emit_at(5, "сч")  # NOP
        emit_at(6, "пб", b6a(a2), mod2)      # переход

    elif op == 0o77:  # стоп
        emit_at(0, "стоп", b6a(a1), mod1)

    elif op == 0o37:  # дпб
        emit_at(0, "пв", b6a(a2), mod2)

    # --- Переходы с РА ---
    elif op == 0o11:  # по < и Ω=1
        emit_at(0, "счи", 0, R_RA)
        emit_at(1, "вч", b6a(a1), mod1)
        emit_at(2, "пио", base + 5, R_OM)   # Ω==0 -> пропуск
        emit_at(3, "пио", b6a(a2), 0)        # ACC<0 -> переход
        emit_at(4, "пб", base + 6)
        emit_at(5, "уиа", b6a(a3), R_RA)
        emit_at(6, "сч")  # NOP

    elif op == 0o31:  # по >= и Ω=1
        emit_at(0, "счи", 0, R_RA)
        emit_at(1, "вч", b6a(a1), mod1)
        emit_at(2, "пио", base + 5, R_OM)
        emit_at(3, "пио", base + 6, 0)      # ACC<0 -> пропуск
        emit_at(4, "пб", b6a(a2), mod2)
        emit_at(5, "уиа", b6a(a3), R_RA)
        emit_at(6, "сч")  # NOP

    elif op == 0o51:  # по < и Ω=0
        emit_at(0, "счи", 0, R_RA)
        emit_at(1, "вч", b6a(a1), mod1)
        emit_at(2, "пино", base + 5, R_OM)  # Ω==1 -> пропуск
        emit_at(3, "пио", b6a(a2), 0)
        emit_at(4, "пб", base + 6)
        emit_at(5, "уиа", b6a(a3), R_RA)
        emit_at(6, "сч")  # NOP

    elif op == 0o71:  # по >= и Ω=0
        emit_at(0, "счи", 0, R_RA)
        emit_at(1, "вч", b6a(a1), mod1)
        emit_at(2, "пино", base + 5, R_OM)
        emit_at(3, "пио", base + 6, 0)
        emit_at(4, "пб", b6a(a2), mod2)
        emit_at(5, "уиа", b6a(a3), R_RA)
        emit_at(6, "сч")  # NOP

    elif op == 0o12:  # по <
        emit_at(0, "счи", 0, R_RA)
        emit_at(1, "вч", b6a(a1), mod1)
        emit_at(2, "пио", b6a(a2), 0)
        emit_at(3, "уиа", b6a(a3), R_RA)

    elif op == 0o32:  # по >=
        emit_at(0, "счи", 0, R_RA)
        emit_at(1, "вч", b6a(a1), mod1)
        emit_at(2, "пио", base + 5, 0)      # ACC<0 -> пропуск
        emit_at(3, "пб", b6a(a2), mod2)
        emit_at(4, "уиа", b6a(a3), R_RA)
        emit_at(5, "сч")  # NOP

    elif op == 0o52:  # установка РА адресом
        emit_at(0, "уиа", b6a(a2), R_RA)

    elif op == 0o72:  # установка РА числом из памяти
        emit_at(0, "сч", b6a(a2), mod2)
        emit_at(1, "мод", T_TMP)
        emit_at(2, "уиа", 0, R_RA)

    # --- Арифметика ---
    elif op in (0o01, 0o21, 0o41, 0o61):  # с
        emit_at(0, "сч", b6a(a1), mod1)
        emit_at(1, "сл", b6a(a2), mod2)
        emit_at(2, "зп", b6a(a3), mod3)
        emit_at(3, "пио", base + 5, 0)      # ACC<0 -> Ω=1
        emit_at(4, "пб", base + 6)
        emit_at(5, "уиа", 1, R_OM)
        emit_at(6, "уиа", 0, R_OM)
        emit_at(7, "сч")  # NOP

    elif op in (0o02, 0o22, 0o42, 0o62):  # в
        emit_at(0, "сч", b6a(a1), mod1)
        emit_at(1, "вч", b6a(a2), mod2)
        emit_at(2, "зп", b6a(a3), mod3)
        emit_at(3, "пио", base + 5, 0)
        emit_at(4, "пб", base + 6)
        emit_at(5, "уиа", 1, R_OM)
        emit_at(6, "уиа", 0, R_OM)
        emit_at(7, "сч")  # NOP

    elif op in (0o03, 0o23, 0o43, 0o63):  # ва
        emit_at(0, "сч", b6a(a1), mod1)
        emit_at(1, "вч", b6a(a2), mod2)
        emit_at(2, "зп", b6a(a3), mod3)
        emit_at(3, "пио", base + 5, 0)
        emit_at(4, "пб", base + 6)
        emit_at(5, "уиа", 1, R_OM)
        emit_at(6, "уиа", 0, R_OM)
        emit_at(7, "сч")  # NOP

    elif op in (0o05, 0o25, 0o45, 0o65):  # у
        emit_at(0, "сч", b6a(a1), mod1)
        emit_at(1, "умн", b6a(a2), mod2)
        emit_at(2, "зп", b6a(a3), mod3)
        emit_at(3, "уиа", 0, R_OM)

    elif op in (0o04, 0o24):  # д
        emit_at(0, "сч", b6a(a1), mod1)
        emit_at(1, "дел", b6a(a2), mod2)
        emit_at(2, "зп", b6a(a3), mod3)
        emit_at(3, "уиа", 0, R_OM)

    elif op in (0o44, 0o64):  # к
        emit_at(0, "сч", b6a(a1), mod1)
        emit_at(1, "зп", b6a(a3), mod3)
        emit_at(2, "уиа", 0, R_OM)

    elif op == 0o47:  # мрп
        emit_at(0, "счи", 0, R_RMR)
        emit_at(1, "зп", b6a(a3), mod3)

    elif op in (0o06, 0o26, 0o46, 0o66):  # спа/спп/впа/впп
        emit_at(0, "сч", b6a(a2), mod2)
        emit_at(1, "зп", b6a(a3), mod3)

    # --- Ввод-вывод ---
    elif op == 0o20:  # счп
        emit_at(0, "сч", 0)
        emit_at(1, "зп", b6a(a3), mod3)

    elif op in (0o10, 0o30):  # ввод с перфокарт
        emit_at(0, "сч", 0)
        emit_at(1, "зп", b6a(a3), mod3)

    elif op == 0o50:  # МА
        pass  # NOP

    elif op == 0o70:  # МБ
        emit_at(0, "сч", 0)
        emit_at(1, "зп", b6a(a3), mod3)

    else:
        emit_at(0, "сч", 0)

    return out

def m20_to_b6_data(word):
    tag = (word >> 44) & 1
    sign = (word >> 43) & 1
    exp = (word >> 37) & 0o77
    mant = word & 0o777777777777
    if exp == 0 and mant == 0:
        return 0
    b6_exp = exp - 32 + 16
    if b6_exp < 0:
        b6_exp = 0
    if b6_exp > 31:
        b6_exp = 31
    b6_mant = mant << 5
    return (sign << 47) | (b6_exp << 41) | b6_mant

def main():
    if len(sys.argv) < 2:
        print("Вызов: translate.py infile.m20 [-o outfile.b6]")
        sys.exit(1)

    infile = sys.argv[1]
    outfile = None
    if '-o' in sys.argv:
        outfile = sys.argv[sys.argv.index('-o') + 1]

    mem, start = load_m20(infile)
    print(f"Загружено {len(mem)} слов, стартовый адрес {start:04o}", file=sys.stderr)

    ops = Counter(w.mnem for w in mem.values() if w.is_code())
    print("Частота команд М-20:", file=sys.stderr)
    for mnem, cnt in ops.most_common(25):
        print(f"  {mnem:5s}: {cnt}", file=sys.stderr)

    # Трансляция
    result = []
    result.append(f"п {b6a(start):05o}")

    for addr in sorted(mem.keys()):
        w = mem[addr]
        if not w.is_code():
            b6word = m20_to_b6_data(w.value)
            result.append(f"в {b6a(addr):05o}")
            result.append(f"с {b6word:016o}")
            continue
        
        cmds = translate_word(w)
        # Сортируем по адресу ячейки
        cmds.sort(key=lambda x: x[0])
        
        # Группируем по адресу
        current_addr = None
        for cell_addr, cmd_str in cmds:
            if cell_addr != current_addr:
                result.append(f"в {cell_addr:05o}")
                current_addr = cell_addr
            result.append(f"к {cmd_str}")

    output = '\n'.join(result) + '\n'
    if outfile:
        with open(outfile, 'w') as f:
            f.write(output)
        print(f"Записано {outfile}", file=sys.stderr)
    else:
        print(output)

if __name__ == '__main__':
    main()
