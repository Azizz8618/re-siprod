#!/bin/sh
# Полные тесты блок-схем ДРАКОН.
#
#   1. модульные тесты генератора разметки (tests/drakon/test_markup.py):
#      разбор ключевых слов, геометрия икон и линий, правила разметки;
#   2. отрицательный тест: пустая схема - ошибка генератора;
#   3. сквозные тесты: разметка -> печать на АЦПУ средствами СИПРОДа
#      (эмулятор dispak, диск 2348), сверка с золотыми эталонами *.out.
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

echo "== модульные тесты генератора разметки =="
if ! python3 "$D/test_markup.py"; then
    fail=1
fi

echo "== отрицательный тест: пустая схема =="
printf '* только комментарий, икон нет\n' > "$work/empty.drakon"
if python3 "$ROOT/tools/drakon_markup.py" "$work/empty.drakon" \
        > "$work/empty.out" 2> "$work/empty.err"; then
    echo "FAIL пустая схема прошла без ошибки"
    fail=1
else
    echo "ok   пустая схема отвергнута: $(cat "$work/empty.err")"
fi

echo "== сквозные тесты: разметка -> СИПРОД -> АЦПУ =="
for src in "$D"/*.drakon; do
    name=$(basename "$src" .drakon)
    python3 "$ROOT/tools/drakon_markup.py" "$src" > "$work/markup.txt"
    "$ROOT/tests/siprod/run.sh" "$work/markup.txt" 2>&1 |
        sed -e 's/[[:space:]]*$//' | grep -v '^$' > "$work/out.txt"
    if grep -q "ERROR NR" "$work/out.txt"; then
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
    else
        echo "нет эталона: $exp (создайте: cp $work/out.txt $exp)"
        fail=1
        continue
    fi
    echo "ok   $name ($(wc -l < "$work/out.txt") строк вывода)"
done
exit $fail
