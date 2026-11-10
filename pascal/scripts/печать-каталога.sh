#!/bin/bash
# Боевая печать каталога схем pascal/схемы (07-22) на АЦПУ ОДНИМ заданием:
# редактор *RED с тома 2348, и исходник каждой схемы подаётся блоком *DRK
# (встроенный режим ДРАКОН) прямо в редакторе - транслятор drakon.pas
# и промежуточная разметка не нужны.
#
#   *DRK <схема 07> *E
#   *DRK <схема 08> *E
#   ...
#   *DRK <схема 22> *E
#   *END
#
# Результат: pascal/схемы/печать-каталог.txt
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.." || exit 1
export DISPAK="${DISPAK:-/home/z/my-project/work/dispak/build/dispak/dispak}"
export BESM6_PATH="${BESM6_PATH:-/home/z/my-project/work/vol:$HOME/.besm6:/tmp}"

: > /tmp/каталог-drk.txt
for f in схемы/0*.drakon схемы/1*.drakon схемы/2*.drakon; do
    echo "== $f" >&2
    echo '*DRK' >> /tmp/каталог-drk.txt
    # в наборе ГОСТ-10859 нет Ё: заменяем Е, иначе слово распадается
    sed 's/[ёЁ]/Е/g' "$f" >> /tmp/каталог-drk.txt
    echo '*E' >> /tmp/каталог-drk.txt
done
echo '*END' >> /tmp/каталог-drk.txt

./scripts/прогнать-с-тома.sh redakt /tmp/каталог-drk.txt > схемы/печать-каталог.txt
echo "печать-каталог.txt: $(wc -l < схемы/печать-каталог.txt) строк"
