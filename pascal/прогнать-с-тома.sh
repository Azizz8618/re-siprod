#!/bin/sh
# Прогон текста через редактор *RED (или транслятор ДРАКОН), загружаемые
# С ТОМА 2348 из библиотеки, записанной записью-2348.sh (зона 2150(8)).
# Компиляция не нужна: модуль читается с диска картой *call.
#
# usage: прогнать-с-тома.sh [redakt|drakon] <файл-текста>
#   печатает выдачу программы (между эхом карты *call и КОНЕЦ ЗАДАЧИ);
#   без выдачи - полный журнал dispak в stderr.
#
# Переменные окружения:
#   DISPAK      путь к dispak (по умолчанию - из PATH)
#   BESM6_PATH  каталоги с образами томов; нужен том 2348 с библиотекой
set -u
DISPAK="${DISPAK:-dispak}"
export BESM6_PATH="${BESM6_PATH:-$HOME/.besm6:/usr/local/share/besm6}"
MOD="${1:-redakt}"
case "$MOD" in
    redakt|drakon) shift ;;
    *) MOD=redakt ;;
esac
[ $# -ge 1 ] || { echo "usage: $0 [redakt|drakon] <файл-текста>" >&2; exit 1; }
TXT="$1"
[ -f "$TXT" ] || { echo "нет файла $TXT" >&2; exit 1; }
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
# текст готовится к перфокартам ГОСТ-10859: верхний регистр, Ё->Е
sed 's/[ёЁ]/Е/g; s/[«»]/"/g; s/—/-/g; s/–/-/g; s/…/.../g' "$TXT" \
    | tr '[:lower:]' '[:upper:]' > "$W/text.gost"
{
    echo "user 419999 зс5^"
    echo "лен 40(2348)^"
    echo "ЕЕВ1А3"
    echo "*name"
    echo "*call yesmemory"
    echo "*perso:402150"
    echo "*call $MOD"
    cat "$W/text.gost"
    echo "*end file"
    echo '``````'
    echo 'ЕКОНЕЦ'
} > "$W/job.b6"
cd "$W"
timeout 600 "$DISPAK" job.b6 > out.txt 2>&1
RC=$?
# выдача задачи: после эха карты *call (первая карта после *perso) и до
# КОНЕЦ ЗАДАЧИ или эха карты *end file (*ЕND)
awk 'f==0 && /402150/{p=1;next} p && /^[ \t]*\*/{f=1;p=0;next} f && (/КОНЕЦ ЗАДАЧИ/ || /^[ \t]*\*ЕND/){f=0} f' out.txt > prog.out
if [ -s prog.out ]; then
    cat prog.out
else
    echo "--- нет выдачи программы; вывод dispak: ---" >&2
    cat out.txt >&2
fi
exit $RC
