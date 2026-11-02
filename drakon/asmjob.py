#!/usr/bin/env python3
"""Сборка модуля ДРАКОН на автокоде БЕМШ (МАКРО-БЕМШ -> объектный модуль).

Задание для транслятора МАКРО-БЕМШ выполняется эмулятором dispak; объектный
модуль записывается в зону тома PERSO (2248), где живёт библиотека СИПРОДа.

Использование:
    python3 drakon/asmjob.py ИСХОДНИК.be [ЗОНА] [ТОМ] [ДЛИНА_ЗОН]
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def make_job(src, zone, tape, length, vol="2248"):
    """Текст .be -> задание для транслятора (карты завершаются знаком ^)."""
    job = ["шифр 419999^", "трак 64^", "лент 30(2048-6200)^", "лент 42(2099)^",
           "лент %s(%s-ЗП)^" % (tape, vol), "ацп 40^", "росп 0^", "врем 240^",
           "лист 0-37^", "вход 4000^", "е", "в 4000", "к 00 010 4003",
           "к 15 24 04000", "к 00 066 0001 00 000 0100", "с 3000 67", "в 14000",
           "а1", "ВВД$$$"]
    for line in open(src, encoding="utf-8").read().rstrip("\n").splitlines():
        line = re.sub(r" {2,},.*$", "", line)      # комментарии убираем
        line = "*" if not line.strip() else line
        job.append(line + "^")
    job += ["КВЧ$$$^", "ТРН$$$^", "ЧТКОМП420070^", "1-1^", "БТМАЛФ^",
            "ЗОНМОД%s%s  00%s^" % (tape, zone, length), "КНЦ$$$^", "_$ЕКОНЕЦ"]
    return "\n".join(job) + "\n"


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        HERE, "src", "drakon.be")
    zone = sys.argv[2] if len(sys.argv) > 2 else "2728"
    tape = sys.argv[3] if len(sys.argv) > 3 else "27"
    length = sys.argv[4] if len(sys.argv) > 4 else "01"
    vol = sys.argv[5] if len(sys.argv) > 5 else "2248"
    job = os.path.splitext(src)[0] + ".b6"
    open(job, "w", encoding="utf-8").write(make_job(src, zone, tape, length, vol))
    print("задание:", job)
    r = subprocess.run(["dispak", job], capture_output=True, text=True)
    out = r.stdout + r.stderr
    for line in out.splitlines():
        if any(k in line for k in ("ОШИБ", "ЧУЖОЙ", "ЗАПИСАН", "ЗОНМОД",
                                  "МОДУЛЬ", "ЗАГР", "ЧИСЛО ОШ", "НЕТ ")):
            print("   ", line.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
