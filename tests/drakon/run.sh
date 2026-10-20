#!/bin/sh
# Сквозной тест: разметка ДРАКОН -> печать на АЦПУ средствами СИПРОДа.
#
#   tools/drakon_markup.py  - эталонный генератор разметки (спецификация
#                             того, что должен выдавать модуль-редактор)
#   tests/siprod/run.sh     - печать разметки средствами СИПРОДа
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
D=$ROOT/tests/drakon
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

fail=0
for src in "$D"/*.drakon; do
    name=$(basename "$src" .drakon)
    python3 "$ROOT/tools/drakon_markup.py" "$src" > "$work/markup.txt"
    "$ROOT/tests/siprod/run.sh" "$work/markup.txt" 2>&1 |
        sed -e 's/[[:space:]]*$//' | grep -v '^$' > "$work/out.txt"
    if grep -q "ОШИБК" "$work/out.txt"; then
        echo "ошибка печати: $name"
        fail=1
        continue
    fi
    # в выводе должна быть рамка схемы и текст иконок
    if ! grep -q "+--" "$work/out.txt"; then
        echo "нет рамок в выводе: $name"
        fail=1
        continue
    fi
    # сверка с эталоном, если он есть
    exp="$D/$name.out"
    if [ -f "$exp" ]; then
        if ! diff -q "$exp" "$work/out.txt" >/dev/null; then
            echo "расхождение с эталоном: $name"
            diff "$exp" "$work/out.txt" | head -5
            fail=1
            continue
        fi
    fi
    echo "ok   $name ($(wc -l < "$work/out.txt") строк вывода)"
done
exit $fail
