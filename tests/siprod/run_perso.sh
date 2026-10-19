#!/bin/sh
# Запуск СИПРОДа из библиотеки, записанной в PERSO на дисковом томе.
#
# Библиотека siprod.bin (PERSO зоны 2702 тома 2248) записывается в
# свободные зоны рабочей копии тома, и СИПРОД запускается уже оттуда.
# Так проверяется, что образ библиотеки, разобранный и собранный
# инструментами проекта, остаётся рабочим.
#
# Использование: tests/siprod/run_perso.sh [-z ZONE] [-l LIBRARY] INPUT
#   INPUT   файл с входом СИПРОДа (всё после *EXECUTE)
#   -z ZONE начальная зона PERSO в рабочей копии тома (по умолчанию 3900)
#   -l LIB  образ библиотеки (по умолчанию siprod.bin)
#
# Переменная окружения SIPROD_WORK задаёт готовую рабочую копию тома
# (если она не задана, копия тома делается заново).
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
ZONE=3900
LIB=$ROOT/siprod.bin
while [ $# -gt 0 ]; do
    case $1 in
    -z) ZONE=$2; shift 2 ;;
    -l) LIB=$2; shift 2 ;;
    *) break ;;
    esac
done
[ $# -eq 1 ] || { echo "usage: $0 [-z ZONE] [-l LIB] INPUT" >&2; exit 2; }
INPUT=$1

if [ -n "${SIPROD_WORK:-}" ]; then
    work=$SIPROD_WORK
else
    work=$(mktemp -d)
    trap 'rm -rf "$work"' EXIT
    # рабочая копия тома 2248: системные образы не изменяются
    cp /usr/local/share/besm6/2248 "$work/2248"
fi
BESM6_PATH="$work:/usr/local/share/besm6"
export BESM6_PATH
python3 "$ROOT/tools/siprod_perso.py" --vol=2248 --zone="$ZONE" \
    --image="$LIB" --work="$work" >/dev/null

# зоны монитора задаются в восьмеричной системе
z=$(printf '%o' "$ZONE")
{
    echo "ШИФР 419900ЗС5^ОЗУ 32^ТРА 100^АЦП 64^ЛЕН 67(2248)^ЕЕВ1А3"
    echo '*name'
    echo '*no lo'
    echo "*perso:67$z"
    echo '*call yesmemory'
    echo '*main schema'
    echo '*execute'
    cat "$INPUT"
    echo '*end file'
    echo '``````'
    echo 'ЕКОНЕЦ'
} > "$work/job.b6"

(cd "$work" && dispak job.b6) > "$work/out.txt" 2>&1 || true
sed -e '1,/\*Е[XХ]Е[CС]UТЕ/d' -e '/^ КОНЕЦ ЗАДАЧИ/,$d' "$work/out.txt"
