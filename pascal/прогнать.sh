#!/bin/bash
# Трансляция и выполнение Паскаль-программы компилятором pascal-re
# (PASCOMPL 15.1 из PERSO тома 2348, зона 2000(8)) под эмулятором dispak.
#
# usage: прогнать.sh <файл.pas> [файл-данных]
#   печатает выдачу программы (между эхом *EXECUTE и КОНЕЦ ЗАДАЧИ);
#   без выдачи - полный журнал dispak в stderr.
#
# Переменные окружения:
#   DISPAK     путь к исполняемому файлу dispak
#   BESM6_PATH список каталогов с образами томов; нужны том 2348
#              (PERSO-библиотека Паскаля) и служебные тома dispak
#              (2053 и др. из build/dispak)
set -u
DISPAK="${DISPAK:-dispak}"
export BESM6_PATH="${BESM6_PATH:-$HOME/.besm6:/tmp}"
PAS="$1"; DATA="${2:-}"
[ -f "$PAS" ] || { echo "нет файла $PAS" >&2; exit 1; }
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
{
    echo "user 419999 зс5^"
    echo "лен 40(2348)^"
    echo "eeв1а3"
    echo "*name"
    echo "*no lo"
    echo "*call yesmemory"
    echo "*perso:402570"
    echo "*stand"
    echo "*call *pascal"
    cat "$PAS"
    echo "*execute"
    [ -n "$DATA" ] && cat "$DATA"
    echo "*end file"
    echo '``````'
    echo 'ЕКОНЕЦ'
} > "$W/job.b6"
cd "$W"
timeout 900 "$DISPAK" job.b6 > out.txt 2>&1
RC=$?
# выдача задачи: между эхом *EXECUTE и "КОНЕЦ ЗАДАЧИ"
awk '/^[ \t]*\*ЕХЕСUТЕ/{f=1;next} /^[ \t]*КОНЕЦ ЗАДАЧИ/{f=0} f' out.txt > prog.out
if [ -s prog.out ]; then
    cat prog.out
else
    echo "--- нет выдачи программы; вывод dispak: ---" >&2
    cat out.txt >&2
fi
exit $RC
