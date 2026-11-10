#!/bin/bash
# Перегенерация эталонных рисунков ДРАКОН (.txt) прогоном drakon.pas
# с тома 2348 (зона 2150(8)).  Эталон = склеенные строки рисунка
# (как их печатает АЦПУ), без хвостовых пробелов.
#
# usage: перегенерировать-эталоны.sh [<имя схемы> ...]
#   без аргументов - все: схемы 01-06 (../drakon/schemes),
#   07-22 (схемы/), demo5-дракон, demo6-силуэт (demo/).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
export DISPAK="${DISPAK:-dispak}"
export BESM6_PATH="${BESM6_PATH:-$HOME/.besm6:/usr/local/share/besm6:/tmp}"
REPO="$(cd "$HERE/../.." && pwd)"

glue() {
    # выдача программы -> строки рисунка
    python3 - "$1" "$2" <<'PYEOF'
import sys
out = []
for l in open(sys.argv[1], errors='replace'):
    l = l.rstrip('\n')
    if l.startswith('*/*D'):
        out.append(l[4:])
    elif l.startswith('*D'):
        if out:
            out[-1] = out[-1].ljust(76) + l[2:]
while out and not out[-1].strip():
    out.pop()
open(sys.argv[2], 'w').write('\n'.join(r.rstrip() for r in out) + '\n')
PYEOF
}

run() {  # run <путь-к-scheme.drakon> <путь-к-эталону.txt>
    local s="$1" t="$2"
    "$HERE/прогнать-с-тома.sh" drakon "$s" > /tmp/regen.out 2>/tmp/regen.err
    if ! grep -q '/\*D' /tmp/regen.out; then
        echo "ОШИБКА $s:"; head -5 /tmp/regen.out /tmp/regen.err
        return 1
    fi
    glue /tmp/regen.out "$t"
    local n=$(wc -l < "$t")
    echo "OK   $t ($n строк)"
}

red() {  # red <кейс.txt> - эталон печати редактора (СИПРОД-П) для секции red
    local t="$1" b
    b=$(basename "$t" .txt)
    mkdir -p "$REPO/pascal/red-эталоны"
    "$HERE/прогнать-с-тома.sh" redakt "$t" > /tmp/regen-red.out 2>/dev/null
    python3 - "$b" /tmp/regen-red.out "$REPO/pascal/red-эталоны/$b.out" <<'PYEOF'
import sys
base, raw, refpath = sys.argv[1], sys.argv[2], sys.argv[3]
txt = open(raw, encoding='utf-8').read()
i = txt.rfind('*ЕХЕСUТЕ')
seg = (txt[i:].split('\n')[1:] if i >= 0 else txt.split('\n'))
out = []
for l in seg:
    s = l.rstrip()
    if 'КОНЕЦ ЗАДАЧИ' in s or s.startswith(' 00'):
        break
    out.append(s)
while out and not out[0]:
    out.pop(0)
while out and not out[-1]:
    out.pop()
open(refpath, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
print('OK   %s.out (%d строк)' % (base, len(out)))
PYEOF
}

cd "$HERE"
if [ $# -gt 0 ]; then
    for s in "$@"; do
        case "$s" in
            red) for f in "$REPO"/tests/siprod/cases/red-*.txt; do red "$f"; done; exit 0 ;;
            0[1-6]-*) run "$REPO/drakon/schemes/$s.drakon" "$REPO/drakon/schemes/${s%.drakon}.txt" ;;
            demo*) run "$HERE/../demo/$s.drakon" "$HERE/../demo/${s%-*}-разметка.txt" ;;
            *) run "$HERE/../схемы/$s.drakon" "$HERE/../схемы/${s%.drakon}.txt" ;;
        esac
    done
    exit 0
fi
for s in "$REPO"/drakon/schemes/0*.drakon; do
    b=$(basename "$s" .drakon)
    run "$s" "$REPO/drakon/schemes/$b.txt"
done
for s in "$HERE"/../схемы/0*.drakon "$HERE"/../схемы/1*.drakon "$HERE"/../схемы/2*.drakon; do
    b=$(basename "$s" .drakon)
    run "$s" "$HERE/../схемы/$b.txt"
done
run "$HERE/../demo/demo5-дракон.txt" "$HERE/../demo/demo5-разметка.txt"
run "$HERE/../demo/demo6-силуэт.drakon" "$HERE/../demo/demo6-разметка.txt"
