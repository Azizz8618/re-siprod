#!/bin/bash
# Регрессионный прогон редактора redakt.pas и транслятора drakon.pas
# по эталонам репозитория re-siprod.
#
# usage: регресс.sh [<путь к re-siprod>]
#   по умолчанию - репозиторий, в котором лежит сама папка pascal;
#   ожидает <re-siprod>/tests/siprod/cases/red-*.txt (+ .out) и
#           <re-siprod>/drakon/schemes/*.drakon (+ .txt)
# Эталон редактора перекрывается собственным: если существует
# <re-siprod>/pascal/red-эталоны/<кейс>.out, сверка идёт с ним.
# Так фиксируются оправданные отличия редактора от оригинала
# (см. README «Отличия от оригинала»): например, red-literal -
# литера Ё печатается как Е (у оригиналов автокода литера теряется).
# Переменные окружения: DISPAK, BESM6_PATH (см. прогнать.sh)
set -u
REPO="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
HERE="$(cd "$(dirname "$0")" && pwd)"
CASES="$REPO/tests/siprod/cases"
ETA="$REPO/pascal/red-эталоны"
SCHEMES="$REPO/drakon/schemes"
ok=0; diff_=0

echo "=== редактор *RED: 21 эталон ==="
for t in "$CASES"/red-*.txt; do
    base=$(basename "$t" .txt)
    out=$(mktemp)
    # перфорация ГОСТ-10859: Ё -> Е (как на пуске с тома и в секции ДРАКОН;
    # эталоны редактора сняты с этой заменой - см. red-эталоны/README)
    sed 's/[ёЁ]/Е/g' "$t" > "$out.dat"
    "$HERE/прогнать.sh" "$HERE/redakt.pas" "$out.dat" > "$out" 2>/dev/null
    ref="$CASES/$base.out"
    etazn=""
    if [ -f "$ETA/$base.out" ]; then
        ref="$ETA/$base.out"
        etazn="  (эталон редактора: red-эталоны/$base.out)"
    fi
    res=$(python3 - "$base" "$out" "$ref" <<'PYEOF'
import sys
base, raw, refpath = sys.argv[1], sys.argv[2], sys.argv[3]
txt = open(raw, encoding='utf-8').read()
i = txt.rfind('*ЕХЕСUТЕ')
seg = (txt[i:].split('\n')[1:] if i >= 0 else txt.split('\n'))
out = []
for l in seg:
    if chr(12) in l:
        continue    # прогон страницы (0201): сверяется отдельно,
                    # в эталонах оригинала его 1-2 на лист
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
    )
    echo "$res"
    case "$res" in
        DIFF*)
            [ -n "$etazn" ] && echo "     $etazn"
            diff_=$((diff_+1))
            ;;
        *)
            ok=$((ok+1))
            ;;
    esac
    rm -f "$out" "$out.dat"
done

echo "=== ДРАКОН: 6 эталонных схем ==="
for s in "$SCHEMES"/*.drakon; do
    base=$(basename "$s" .drakon)
    out=$(mktemp)
    # в наборе ГОСТ-10859 нет Ё: заменяем Е, иначе слово распадается
    sed 's/[ёЁ]/Е/g' "$s" > "$out.dat"
    "$HERE/прогнать.sh" "$HERE/drakon.pas" "$out.dat" > "$out" 2>/dev/null
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

echo "=== ДРАКОН встроенным режимом *DRK: печать = разметке ==="
for s in "$SCHEMES"/*.drakon "$HERE/схемы"/*.drakon; do
    base=$(basename "$s" .drakon)
    out=$(mktemp)
    # в наборе ГОСТ-10859 нет Ё: заменяем Е, иначе слово распадается
    sed 's/[ёЁ]/Е/g' "$s" > "$out.dat"
    # маршрут 1: разметка drakon.pas -> печать редактором
    "$HERE/прогнать.sh" "$HERE/drakon.pas" "$out.dat" > "$out.mk" 2>/dev/null
    "$HERE/прогнать.sh" "$HERE/redakt.pas" "$out.mk" > "$out.red" 2>/dev/null
    # маршрут 2: исходник напрямую блоком *DRK того же редактора
    { echo '*DRK'; cat "$out.dat"; echo '*E'; } > "$out.drk"
    "$HERE/прогнать.sh" "$HERE/redakt.pas" "$out.drk" > "$out.drko" 2>/dev/null
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

echo "=== итог: OK $ok, DIFF $diff_ ==="
[ "$diff_" -eq 0 ]
