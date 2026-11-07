#!/bin/bash
# Секции регресса (регресс.sh целиком длиннее лимита времени вызова):
#   секция red    - редактор *RED: 16 эталонов red-*
#   секция drk6   - ДРАКОН: 6 эталонных схем drakon/schemes
#   секция same   - *DRK = разметка (все схемы: корневые + pascal/схемы)
# usage: секции-регресса.sh red|drk6|same
set -u
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
HERE="$REPO/pascal"
CASES="$REPO/tests/siprod/cases"
SCHEMES="$REPO/drakon/schemes"
export DISPAK="${DISPAK:-/home/z/my-project/work/dispak/build/dispak/dispak}"
export BESM6_PATH="${BESM6_PATH:-$HOME/.besm6:/usr/local/share/besm6:/tmp}"
ok=0; diff_=0
sec="${1:-all}"

if [ "$sec" = red ] || [ "$sec" = all ]; then
echo "=== редактор *RED: 16 эталонов ==="
for t in "$CASES"/red-*.txt; do
    base=$(basename "$t" .txt)
    out=$(mktemp)
    "$HERE/прогнать-с-тома.sh" redakt "$t" > "$out" 2>/dev/null
    python3 - "$base" "$out" "$CASES/$base.out" <<'PYEOF'
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
ref = open(refpath, encoding='utf-8').read().split('\n')
ref = [l.rstrip() for l in ref if not l.startswith('\x0c')]
while ref and not ref[0]:
    ref.pop(0)
while ref and not ref[-1]:
    ref.pop()
if out == ref:
    print('OK   %s' % base)
    sys.exit(0)
else:
    print('DIFF %s  (моя: %d строк, эталон: %d)' % (base, len(out), len(ref)))
    sys.exit(1)
PYEOF
    if [ $? -eq 0 ]; then ok=$((ok+1)); else diff_=$((diff_+1)); fi
    rm -f "$out"
done
fi

if [ "$sec" = drk6 ] || [ "$sec" = all ]; then
echo "=== ДРАКОН: 6 эталонных схем ==="
for s in "$SCHEMES"/*.drakon; do
    base=$(basename "$s" .drakon)
    out=$(mktemp)
    sed 's/[ёЁ]/Е/g' "$s" > "$out.dat"
    "$HERE/прогнать-с-тома.sh" drakon "$out.dat" > "$out" 2>/dev/null
    if python3 "$HERE/сверить-дракон.py" "$out" "$SCHEMES/$base.txt" > "$out.log" 2>&1; then
        echo "OK   $base  $(head -1 "$out.log")"
        ok=$((ok+1))
    else
        echo "DIFF $base"
        head -6 "$out.log"
        diff_=$((diff_+1))
    fi
    rm -f "$out" "$out.dat" "$out.log"
done
fi

if [ "$sec" = same ] || [ "$sec" = all ]; then
echo "=== ДРАКОН встроенным режимом *DRK: печать = разметке ==="
for s in "$SCHEMES"/*.drakon "$HERE/схемы"/*.drakon; do
    base=$(basename "$s" .drakon)
    out=$(mktemp)
    sed 's/[ёЁ]/Е/g' "$s" > "$out.dat"
    "$HERE/прогнать-с-тома.sh" drakon "$out.dat" > "$out.mk" 2>/dev/null
    "$HERE/прогнать-с-тома.sh" redakt "$out.mk" > "$out.red" 2>/dev/null
    { echo '*DRK'; cat "$out.dat"; echo '*E'; } > "$out.drk"
    "$HERE/прогнать-с-тома.sh" redakt "$out.drk" > "$out.drko" 2>/dev/null
    if diff -q "$out.red" "$out.drko" >/dev/null; then
        echo "OK   $base  (*DRK = разметка, $(wc -l < "$out.drko") строк)"
        ok=$((ok+1))
    else
        echo "DIFF $base (*DRK != разметка)"
        diff "$out.red" "$out.drko" | head -6
        diff_=$((diff_+1))
    fi
    rm -f "$out" "$out.dat" "$out.mk" "$out.red" "$out.drk" "$out.drko"
done
fi

echo "=== итог секции $sec: OK $ok, DIFF $diff_ ==="
[ "$diff_" -eq 0 ]
