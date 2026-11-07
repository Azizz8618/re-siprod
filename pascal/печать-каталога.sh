#!/bin/bash
# Печать каталога схем pascal/схемы (07-22) на АЦПУ связкой:
# drakon (разметка с тома 2348) -> redakt (печать с тома).
# Результат: pascal/схемы/печать-каталог.txt
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE" || exit 1
export DISPAK="${DISPAK:-/home/z/my-project/work/dispak/build/dispak/dispak}"
export BESM6_PATH="${BESM6_PATH:-/home/z/my-project/work/vol:$HOME/.besm6:/tmp}"
: > /tmp/каталог.txt
for f in схемы/0*.drakon схемы/1*.drakon схемы/2*.drakon; do
    echo "== $f" >&2
    ./прогнать-с-тома.sh drakon "$f" >> /tmp/каталог.txt 2>/dev/null || {
        echo "ОШИБКА drakon $f" >&2; exit 1; }
done
echo '*END' >> /tmp/каталог.txt
./прогнать-с-тома.sh redakt /tmp/каталог.txt > схемы/печать-каталог.txt
echo "печать-каталог.txt: $(wc -l < схемы/печать-каталог.txt) строк"
