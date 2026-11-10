#!/usr/bin/env python3
# Сверка прогона одного кейса с эталоном: та же фильтрация, что в регресс.sh,
# но с построчным diff (единообразно для отладки частей 1-3).
# usage: сверка.py <case-имя>          (относительно tests/siprod/cases)
import sys, os, subprocess

case = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
casef = f"{REPO}/tests/siprod/cases/{case}.txt"
env = dict(os.environ)
env.setdefault("DISPAK", "/home/z/my-project/dispak/build/dispak/dispak")
env.setdefault("BESM6_PATH", os.path.expanduser("~/.besm6:/tmp"))
raw = subprocess.run([f"{HERE}/прогнать.sh", f"{HERE}/../source/redakt.pas", casef],
                     env=env, capture_output=True, text=True).stdout

def filtr(txt):
    lines = txt.split('\n')
    i = txt.rfind('*ЕХЕСUТЕ')
    seg = (txt[i:].split('\n')[1:] if i >= 0 else lines)
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

ref = open(f"{REPO}/tests/siprod/cases/{case}.out", encoding='utf-8').read().split('\n')
ref = [l.rstrip() for l in ref if not l.startswith('\x0c')]
while ref and not ref[0]:
    ref.pop(0)
while ref and not ref[-1]:
    ref.pop()
mine = filtr(raw)
print(f"моя: {len(mine)} строк, эталон: {len(ref)} строк")
if mine == ref:
    print("СОВПАДАЕТ")
else:
    # первый diff
    import difflib
    n = 0
    for line in difflib.unified_diff(ref, mine, 'эталон', 'моя', lineterm='', n=2):
        print(line[:130])
        n += 1
        if n > 60:
            print('...')
            break
