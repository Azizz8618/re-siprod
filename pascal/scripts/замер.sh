#!/bin/bash
# Измерение быстродействия редактора *RED (redakt.pas) и транслятора
# ДРАКОН (drakon.pas) на эмуляторе dispak.
#
# Единица измерения - число выполненных команд БЭСМ-6, которое печатает
# dispak -s ("N instructions per T seconds"): счёт детерминирован входом
# и не зависит от скорости хоста.  На реальной БЭСМ-6 (~1 млн оп/с)
# число команд - это примерно секунды.
#
# usage: замер.sh <выходной-каталог>
# Переменные окружения:
#   DISPAK      путь к dispak
#   BESM6_PATH  каталоги с томами: том 2348 с библиотекой (зона 2150(8),
#               запись-2348.sh) и служебные тома dispak
#   REPO        репозиторий re-siprod (по умолчанию - родитель pascal/)
#
# Схема прогона (как в прогнать-с-тома.sh): Монитор-80, библиотека
# редактора с тома (402150) и run-time (402570,cont), редактор картой
# *call - без компиляции.
# Компиляция меряется отдельно (колода с *call *pascal без *execute).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="${REPO:-$(cd "$HERE/../.." && pwd)}"
DISPAK="${DISPAK:-dispak}"
export BESM6_PATH="${BESM6_PATH:-/usr/local/share/besm6}"
CASES="$REPO/tests/siprod/cases"
OUT="${1:?usage: замер.sh <выходной-каталог>}"
mkdir -p "$OUT"
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT

# счёт команд из журнала dispak
instr() { # <журнал> -> число команд
    sed -n 's/^\([0-9][0-9]*\) instructions per.*/\1/p' "$1" | tail -1
}

# задача с тома: модуль redakt|drakon из PERSO 402150, данные - stdin
runfromvol() { # <модуль> <файл-данных> <журнал>
    local mod="$1" data="$2" log="$3"
    sed 's/[ёЁ]/Е/g; s/[«»]/"/g; s/—/-/g; s/–/-/g; s/…/.../g' "$data" \
        | tr '[:lower:]' '[:upper:]' > "$W/text.gost"
    {
        echo "user 419999 зс5^"
        echo "лен 40(2348)^"
        echo "ЕЕВ1А3"
        echo "*name"
        echo "*call yesmemory"
        echo "*perso:402150"
        echo "*perso:402570,cont"
        echo "*call $mod"
        cat "$W/text.gost"
        echo "*end file"
        echo '``````'
        echo 'ЕКОНЕЦ'
    } > "$W/job.b6"
    (cd "$W" && "$DISPAK" -s job.b6) > "$log" 2>&1
}

# трансляция без выполнения (чистая компиляция): PERSO компилятора 402570
compileonly() { # <файл.pas> <журнал>
    local pas="$1" log="$2"
    sed 's/[ёЁ]/Е/g' "$pas" | tr '[:lower:]' '[:upper:]' > "$W/src.gost"
    {
        echo "user 419999 зс5^"
        echo "лен 40(2348)^"
        echo "ЕЕВ1А3"
        echo "*name"
        echo "*no lo"
        echo "*call yesmemory"
        echo "*perso:402570"
        echo "*stand"
        echo "*call *pascal"
        cat "$W/src.gost"
        echo "*end file"
        echo '``````'
        echo 'ЕКОНЕЦ'
    } > "$W/job.b6"
    (cd "$W" && "$DISPAK" -s job.b6) > "$log" 2>&1
}

: > "$OUT/сводка.tsv"
note() { printf '%b\n' "$*" | tee -a "$OUT/сводка.tsv"; }

note "этап\tкоманд\tжурнал"

# ---- 1. компиляция ----
compileonly "$REPO/pascal/source/redakt.pas" "$W/compile-redakt.log"
note "компиляция redakt.pas\t$(instr "$W/compile-redakt.log")\tcompile-redakt.log"
compileonly "$REPO/pascal/source/drakon.pas" "$W/compile-drakon.log"
note "компиляция drakon.pas\t$(instr "$W/compile-drakon.log")\tcompile-drakon.log"

# ---- 2. база: Монитор + загрузка библиотеки + запуск, текст только *END ----
printf '*END\n' > "$W/end.dat"
runfromvol redakt "$W/end.dat" "$W/base-redakt.log"
note "база: Монитор+загрузка+старт\t$(instr "$W/base-redakt.log")\tbase-redakt.log"

# ---- 3. эталоны red-*: редактор с тома ----
for t in "$CASES"/red-*.txt; do
    b=$(basename "$t" .txt)
    runfromvol redakt "$t" "$W/pas-$b.log"
    note "редактор: $b\t$(instr "$W/pas-$b.log")\tpas-$b.log"
done

# ---- 4. оригинальный СИПРОД на тех же эталонах (run.sh -r -x -s) ----
ORIGLOG=$(mktemp -d)
export BESM6_SHARE="${BESM6_SHARE:-$(echo "$BESM6_PATH" | cut -d: -f1)}"
export PATH="$PATH:$(dirname "$(command -v "$DISPAK")")"
for t in "$CASES"/red-*.txt; do
    b=$(basename "$t" .txt)
    "$REPO/tests/siprod/run.sh" -r -x -s "$t" > "$ORIGLOG/$b.log" 2>&1 || true
    note "оригинал: $b\t$(instr "$ORIGLOG/$b.log")\torig-$b.log"
done

# ---- 5. транслятор ДРАКОН: эталонные схемы ----
for s in "$REPO/drakon/schemes"/*.drakon; do
    b=$(basename "$s" .drakon)
    sed 's/[ёЁ]/Е/g' "$s" > "$W/scheme.dat"
    runfromvol drakon "$W/scheme.dat" "$W/drk-$b.log"
    note "дракон: $b\t$(instr "$W/drk-$b.log")\tdrk-$b.log"
done

# ---- 6. масштабирование: генерация плотного текста 50..400 карт ----
for n in 50 100 200 400; do
    {
        echo '*RED'
        for i in $(seq 1 "$n"); do
            echo 'ОДИН ДВА ТРИ ЧЕТЫРЕ ПЯТЬ ШЕСТЬ СЕМЬ ВОСЕМЬ ДЕВЯТЬ ДЕСЯТЬ'
        done
        echo '*E'
        echo '*END'
    } > "$W/scale-$n.dat"
    runfromvol redakt "$W/scale-$n.dat" "$W/scale-pas-$n.log"
    note "масштаб $n карт: редактор\t$(instr "$W/scale-pas-$n.log")\tscale-pas-$n.log"
    "$REPO/tests/siprod/run.sh" -r -x -s "$W/scale-$n.dat" \
        > "$W/scale-orig-$n.log" 2>&1 || true
    note "масштаб $n карт: оригинал\t$(instr "$W/scale-orig-$n.log")\tscale-orig-$n.log"
done

# ---- 7. профиль по кодам операций (-ss) ----
sed 's/[ёЁ]/Е/g' "$CASES/red-fill.txt" > "$W/text.gost"
{
    echo "user 419999 зс5^"
    echo "лен 40(2348)^"
    echo "ЕЕВ1А3"
    echo "*name"
    echo "*call yesmemory"
    echo "*perso:402150"
    echo "*perso:402570,cont"
    echo "*call redakt"
    cat "$W/text.gost"
    echo "*end file"
    echo '``````'
    echo 'ЕКОНЕЦ'
} > "$W/job-fill.b6"
(cd "$W" && "$DISPAK" -ss job-fill.b6) > "$W/profile-pas-fill.log" 2>&1 || true
"$REPO/tests/siprod/run.sh" -r -x -ss "$CASES/red-fill.txt" \
    > "$W/profile-orig-fill.log" 2>&1 || true
echo "профили: $W/profile-pas-fill.log $W/profile-orig-fill.log"

cp "$W"/profile-*.log "$OUT/" 2>/dev/null
cp "$W"/scale-*.log "$OUT/" 2>/dev/null
cp "$W"/compile-*.log "$OUT/" 2>/dev/null
cp "$W"/base-*.log "$OUT/" 2>/dev/null
for f in "$W"/pas-*.log; do cp "$f" "$OUT/" 2>/dev/null; done
for f in "$ORIGLOG"/*.log; do cp "$f" "$OUT/" 2>/dev/null; done
echo "готово: $OUT/сводка.tsv"
