#!/usr/bin/env python3
# Сверка пробы с живым оригиналом СИПРОДа: оригинал - tests/siprod/run.sh,
# реализация - pascal/прогнать.sh с redakt.pas; обе выдачи фильтруются
# одинаково (без строк прогона, до КОНЕЦ ЗАДАЧИ) и сравниваются.
# usage: сверка-проб.py <файл-пробы> [...]
import sys, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
env = dict(os.environ)
env.setdefault("DISPAK", "/home/z/my-project/dispak/build/dispak/dispak")
env.setdefault("BESM6_PATH", os.path.expanduser("~/.besm6:/tmp"))
env.setdefault("BESM6_SHARE", os.path.expanduser("~/.besm6"))
env["PATH"] = "/home/z/my-project/dispak/build/dispak:/home/z/my-project/dispak/build/besmtool:" + env["PATH"]

def filtr(txt):
    i = txt.rfind('*ЕХЕСUТЕ')
    seg = (txt[i:].split('\n')[1:] if i >= 0 else txt.split('\n'))
    out = []
    for l in seg:
        if chr(12) in l:
            continue
        s = l.rstrip()
        if 'КОНЕЦ ЗАДАЧИ' in s or s.startswith(' 00'):
            break
        out.append(s)
    while out and not out[0]:
        out.pop(0)
    while out and not out[-1]:
        out.pop()
    return out

def ffmark(txt):
    return [i for i, l in enumerate(txt.split('\n'), 1) if chr(12) in l]

ok = 0
for f in sys.argv[1:]:
    orig = subprocess.run([f"{REPO}/tests/siprod/run.sh", f], env=env,
                          capture_output=True, text=True).stdout
    mine = subprocess.run([f"{HERE}/прогнать.sh", f"{HERE}/redakt.pas", f],
                          env=env, capture_output=True, text=True).stdout
    fo, fm = filtr(orig), filtr(mine)
    name = os.path.basename(f)
    if fo == fm:
        print(f"СОВПАДАЕТ  {name}  ({len(fo)} строк)")
        ok += 1
    else:
        print(f"ОТЛИЧАЕТСЯ {name}  (оригинал: {len(fo)}, мой: {len(fm)};"
              f" прогоны ориг/мой: {len(ffmark(orig))}/{len(ffmark(mine))})")
        import difflib
        n = 0
        for line in difflib.unified_diff(fo, fm, 'оригинал', 'мой',
                                         lineterm='', n=1):
            print(' ', line[:120])
            n += 1
            if n > 24:
                print('  ...')
                break
print(f"итого: совпадают {ok} из {len(sys.argv)-1}")
