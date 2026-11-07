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
export DISPAK="${DISPAK:-/home/z/my-project/work/dispak/build/dispak/dispak}"
export BESM6_PATH="${BESM6_PATH:-/home/z/my-project/work/vol:$HOME/.besm6:/tmp}"
REPO="$(cd "$HERE/.." && pwd)"

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

cd "$HERE"
if [ $# -gt 0 ]; then
    for s in "$@"; do
        case "$s" in
            0[1-6]-*) run "$REPO/drakon/schemes/$s.drakon" "$REPO/drakon/schemes/${s%.drakon}.txt" ;;
            demo*) run "demo/$s.drakon" "demo/${s%-*}-разметка.txt" ;;
            *) run "схемы/$s.drakon" "схемы/${s%.drakon}.txt" ;;
        esac
    done
    exit 0
fi
for s in "$REPO"/drakon/schemes/0*.drakon; do
    b=$(basename "$s" .drakon)
    run "$s" "$REPO/drakon/schemes/$b.txt"
done
for s in схемы/0*.drakon схемы/1*.drakon схемы/2*.drakon; do
    b=$(basename "$s" .drakon)
    run "$s" "схемы/$b.txt"
done
run demo/demo5-дракон.txt demo/demo5-разметка.txt
run demo/demo6-силуэт.drakon demo/demo6-разметка.txt
