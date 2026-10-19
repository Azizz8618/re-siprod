#!/bin/sh
# Сравнение работы СИПРОДа из исходной библиотеки (PERSO зоны 2702 тома
# 2248) и из библиотеки, записанной заново tools/siprod_perso.py.
#
# Проверяются два образа: исходный siprod.bin и собранный из
# откомментированных текстов (make build).
# Для каждого примера tests/siprod/cases/ вывод должен совпасть байт в байт.
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
D=$ROOT/tests/siprod
ZONE=${ZONE:-3900}

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
cp /usr/local/share/besm6/2248 "$work/2248"
SIPROD_WORK=$work
export SIPROD_WORK

# библиотека, собранная из откомментированных текстов
if [ ! -f "$ROOT/build/siprod.bin" ]; then
    echo "нет build/siprod.bin - выполните make build" >&2
    exit 1
fi

fail=0
n=0
for lib in "$ROOT/siprod.bin" "$ROOT/build/siprod.bin"; do
    echo "== образ: $lib"
    for f in "$D"/cases/*.txt; do
        b=$(basename "$f" .txt)
        "$D/run.sh" "$f" > "$work/a.txt" 2>&1
        "$D/run_perso.sh" -z "$ZONE" -l "$lib" "$f" > "$work/b.txt" 2>&1
        n=$((n + 1))
        if cmp -s "$work/a.txt" "$work/b.txt"; then
            echo "OK   $b"
        else
            echo "DIFF $b"
            diff "$work/a.txt" "$work/b.txt" | head -5
            fail=$((fail + 1))
        fi
    done
done
echo "примеров: $n, расхождений: $fail"
[ "$fail" -eq 0 ]
