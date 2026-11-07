#!/bin/sh
# Запись библиотеки связки «pascal» на том 2348, зона 2150(8):
# компилятор PASCOMPL 15.1, модули run-time, редактор *RED СИПРОД-П
# (RЕДАКТ; в него встроен режим ДРАКОН - блок *DRK верхнего уровня)
# и транслятор схем ДРАКОН (DRАКОН, канал разметки * /*D).
#
# Метод - «мониторный путь» (как в tools/catchup2348_monitor.sh):
#   задача Монитора-80 монтирует том с правом записи (лен 40(2348-wr)^),
#   загружает PERSO-библиотеку компилятора (*perso:402570^), штатно
#   транслирует redakt.pas и drakon.pas (*call *pascal) и записывает
#   временный каталог задачи обратно на том (*to perso:402150^).
#   Монитор печатает «ДЛИНА LIBRARY 100 ЗОН» (октально, включая каталог;
#   РЕДАКТ вырос после встраивания режима *DRK).
#
# После записи редактор запускается с тома без компиляции:
#
#   лен 40(2348)^
#   *perso:402150
#   *call redakt
#   <текст режима *RED>
#
# Этапы:
#   1) резерв тома рядом с ним (<том>.bak-pascal-<дата>, идемпотентно);
#   2) предпроверка зоны 0o2150: свободна либо занята нашей же библиотекой
#      (перезапись); чужие данные - СТОП;
#   3) колода: исходники к ГОСТ-10859 (верхний регистр, Ё->Е), трансляция
#      обоих источников, *to perso:402150; контроль «ДЛИНА LIBRARY» -
#      библиотека обязана уложиться до зоны 0o2300;
#   4) контроль: каталог зоны 0o2150 содержит РАSСОМРL, RЕДАКТ, DRАКОН;
#      занятые зоны вне области записи не изменились (против резерва);
#   5) smoke: редактор запускается С ТОМА (*perso:402150, *call redakt)
#      на demo/demo1-текст.txt; выдача побайтно равна redakt.out;
#   6) md5 до/после (штамп монитора в шапках зон меняется между
#      сессиями - повторный прогон безопасен и обновляет штампы).
#
# Окружение: DISPAK, BESMTOOL, BESM6_PATH (как в прогнать.sh).  Том 2348
# берётся из BESM6_PATH; запись ведётся в ПЕРВУЮ найденную копию - держите
# рабочую копию впереди боевого тома (см. PERSO.md проекта pascal-re).
#
# Запуск:  sh pascal/запись-2348.sh
set -eu

DISPAK=${DISPAK:-dispak}
BESMTOOL=${BESMTOOL:-besmtool}
U=${HOME:-/home/azizz}
export BESM6_PATH="${BESM6_PATH:-$HOME/.besm6:/usr/local/share/besm6}"
HERE=$(cd "$(dirname "$0")" && pwd)

VOL=2348
LU=40
ZONE=2150          # восьмеричная зона библиотеки на томе
SRC=2570           # PERSO-библиотека компилятора (источник, только чтение)
LIMIT=130          # свободный промежуток: 0o2150 + 0o130 = 0o2300
DEMO=demo/demo1-текст.txt
ETALON=redakt.out

md5f() { md5sum "$1" | cut -d' ' -f1; }
oct() {
    # восьмеричное -> десятичное (POSIX sh не понимает арифметику 8#NNN)
    o=$1; d=0
    while [ -n "$o" ]; do
        d=$(( d * 8 + ${o%"${o#?}"} ))
        o=${o#?}
    done
    echo $d
}
gost() {
    # ГОСТ-10859: в наборе нет строчных букв и Ё - как в собрать-колоду.sh
    sed 's/[ёЁ]/Е/g; s/[«»]/"/g; s/—/-/g; s/–/-/g; s/…/.../g' "$1" \
        | tr '[:lower:]' '[:upper:]'
}

volpath=$(printf '%s\n' "$BESM6_PATH" | tr ':' '\n' | while IFS= read -r d; do
    [ -n "$d" ] || continue
    [ -f "$d/$VOL" ] && { printf '%s\n' "$d/$VOL"; break; }
done)
[ -n "${volpath:-}" ] || { echo "СТОП: том $VOL не найден в BESM6_PATH" >&2; exit 1; }
echo "том: $volpath"
for t in "$DISPAK" "$BESMTOOL"; do
    command -v "$t" >/dev/null || { echo "СТОП: нет $t в PATH" >&2; exit 1; }
done
for f in redakt.pas drakon.pas "$DEMO" "$ETALON"; do
    [ -f "$HERE/$f" ] || { echo "СТОП: нет $HERE/$f" >&2; exit 1; }
done

before=$(md5f "$volpath")
echo "том до: md5 $before"

# 1) Резерв (идемпотентно).  Каталог боевого тома принадлежит root:
#    нового файла резерва там не создать (sudo недоступен), поэтому для
#    неподдающегося каталогу резерв снимается в ~/.besm6, как требует
#    README re-siprod (2348.bak-<цель>-<ГГГГММДД>; прецедент
#    tools/catchup2348_monitor.sh - bak-prod-).  Для каталога
#    пользователя резерв остаётся рядом с томом.
BAK="$volpath.bak-pascal-$(date +%Y%m%d)"
if [ ! -w "$(dirname "$volpath")" ]; then
    BAK="$U/.besm6/2348.bak-pascal-prod-$(date +%Y%m%d)"
fi
if [ ! -f "$BAK" ]; then
    cp -p "$volpath" "$BAK"
    echo "резерв: $BAK md5=$(md5f "$BAK")"
else
    echo "резерв уже есть: $BAK"
fi

# 2) Предпроверка зоны.
ZDEC=$(oct $ZONE)
LMIT=$(oct $LIMIT)
view=$("$BESMTOOL" view "$VOL" --start=$ZDEC --length=1 --encoding=t 2>/dev/null || true)
if printf '%s\n' "$view" | grep -q "$ZONE\."; then
    if printf '%s\n' "$view" | grep -q 'ЕDАК'; then
        echo "зона $ZONE уже занята нашей библиотекой - перезаписываем"
    else
        echo "СТОП: зона $ZONE занята чужими данными:" >&2
        printf '%s\n' "$view" | head -3 >&2
        exit 1
    fi
else
    echo "зона $ZONE свободна - записываем"
fi

# 3) Колода: трансляция двух источников и запись каталога задачи.
W=$(mktemp -d)
trap 'rm -rf "$W"' EXIT
{
    echo "user 419900 зс5^"
    echo "лен $LU($VOL-wr)^"
    echo "ЕЕВ1А3"
    echo "*name"
    echo "*call yesmemory"
    echo "*perso:$LU$SRC"
    echo "*call *pascal"
    gost "$HERE/redakt.pas"
    echo "*call *pascal"
    gost "$HERE/drakon.pas"
    echo "*to perso:$LU$ZONE"
    echo "*end file"
    echo '``````'
    echo 'ЕКОНЕЦ'
} > "$W/write.b6"

out=$(timeout 1800 "$DISPAK" "$W/write.b6" 2>&1) || {
    echo "СТОП: прогон записи не удался (код $?)" >&2
    printf '%s\n' "$out" | tail -15 >&2
    exit 1
}
printf '%s\n' "$out" | grep -a 'ДЛИНА' || true

dlina=$(printf '%s\n' "$out" | grep -a 'ДЛИНА' | grep -a 'ЗОН' | tail -1 \
        | sed 's/.*[^0-7]\([0-7][0-7]*\)[ \t]*ЗОН.*/\1/')
case "$dlina" in
    ''|*[!0-7]*) echo "СТОП: не понял «ДЛИНА LIBRARY ... ЗОН»: '$dlina'" >&2
                 printf '%s\n' "$out" | tail -15 >&2; exit 1 ;;
esac
DL=$(oct "$dlina")
echo "ДЛИНА LIBRARY $dlina ЗОН ($DL зон)"
if [ "$DL" -gt "$LMIT" ]; then
    echo "СТОП: библиотека $DL зон не укладывается в промежуток" \
         "0o$ZONE..$(printf '%o' $((ZDEC + LMIT))); том восстановим из резерва:" >&2
    echo "  cp '$BAK' '$volpath'" >&2
    exit 1
fi

# 4) Контроль каталога и неизменности тома вне области записи.
if "$BESMTOOL" view "$VOL" --start=$ZDEC --length=1 --encoding=t 2>/dev/null \
        | grep -q 'СОМРL' \
   && "$BESMTOOL" view "$VOL" --start=$ZDEC --length=1 --encoding=t 2>/dev/null \
        | grep -q 'ЕDАК' \
   && "$BESMTOOL" view "$VOL" --start=$ZDEC --length=1 --encoding=t 2>/dev/null \
        | grep -q 'АКОN'; then
    echo "каталог зоны 0o$ZONE: РАSСОМРL, RЕDАКТ, DRАКОН на месте"
else
    echo "СТОП: в каталоге зоны 0o$ZONE нет ожидаемых модулей" >&2
    "$BESMTOOL" view "$VOL" --start=$ZDEC --length=1 --encoding=t 2>&1 | head -5 >&2
    exit 1
fi

python3 - "$volpath" "$BAK" "$ZDEC" "$DL" <<'PYEOF'
import sys
Z = 8256
vol, bak, z0, n = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
def zones(p):
    return open(p, 'rb').read()
v, b = zones(vol), zones(bak)
def isfree(z):   # свободная зона: 4 нулевых байта и сигнатура 80c7 f105
    return z[0:4] == b'\0\0\0\0' and z[10:14] == b'\x80\xc7\xf1\x05'
bad = []
for F in range(4, len(v) // Z):
    if z0 <= F - 4 < z0 + n:            # область записи - не проверяем
        continue
    a, c = v[Z*F:Z*(F+1)], b[Z*F:Z*(F+1)]
    if a != c and not (isfree(a) and isfree(c)):
        bad.append(('%o' % (F - 4)))
if bad:
    raise SystemExit('КРИТИЧНО: изменённые занятые зоны вне записи: %s' % bad[:8])
print('   вне области записи занятые зоны не изменены: OK')
PYEOF

# 4б) Обрезка зоны: копия библиотеки компилятора (из 2570) в зоне 2150
#     не нужна - компилятор берётся оттуда же; остаются только модули
#     задачи (РЕДАКТ, ДРАКОН).  Дубликат обнуляется (besmtool zero).
# Обрезка зоны (обнуление копии библиотеки компилятора) - только по
# явному запросу: граница модулей задачи ищется по началу объектного
# модуля, а каталог зоны ещё содержит записи компилятора (иначе монитор
# считает подпрограммы испорченными).  Включается переменной TRIM_ZONE=1.
TRIM="$HERE/../tools/perso_trim.py"
if [ "${TRIM_ZONE:-0}" = "1" ] && [ -f "$TRIM" ]; then
    BESM6_PATH="$BESM6_PATH" python3 "$TRIM" \
        --volume="$VOL" --zone="$ZONE" || {
        echo "СТОП: обрезка зоны не удалась" >&2; exit 1; }
fi

# 5) Smoke: редактор запускается С ТОМА, выдача равна эталону.
gost "$HERE/$DEMO" > "$W/demo.gost"
{
    echo "user 419999 зс5^"
    echo "лен $LU($VOL)^"
    echo "ЕЕВ1А3"
    echo "*name"
    echo "*call yesmemory"
    echo "*perso:$LU$ZONE"
    echo "*call redakt"
    cat "$W/demo.gost"
    echo "*end file"
    echo '``````'
    echo 'ЕКОНЕЦ'
} > "$W/smoke.b6"
timeout 600 "$DISPAK" "$W/smoke.b6" > "$W/smoke.log" 2>&1 || true

python3 - "$W/smoke.log" "$HERE/$ETALON" <<'PYEOF' && SMOKE=ok || SMOKE=нет
import sys
log = open(sys.argv[1], encoding='utf-8').read().split('\n')
perso = next((i for i, l in enumerate(log) if ':402150' in l), None)
if perso is None:
    print('   smoke: в журнале нет карты *perso:402150; начало журнала:')
    for l in log[:6]:
        print('     |', l)
    raise SystemExit(1)
call = next((i for i, l in enumerate(log[perso+1:], perso+1)
             if l.lstrip().startswith('*') and 'LL' in l.replace('Л', 'L')), None)
if call is None:
    raise SystemExit(1)
out = []
for l in log[call+1:]:
    # строка прогона \f значима: не полоскать её в пробел
    s = l if l == chr(12) else l.rstrip()
    if 'КОНЕЦ ЗАДАЧИ' in s:
        break
    out.append(s)
while out and not out[0]:
    out.pop(0)
while out and not out[-1]:
    out.pop()
ref = open(sys.argv[2], encoding='utf-8').read().split('\n')
ref = [l if l == chr(12) else l.rstrip() for l in ref]
while ref and not ref[0]:
    ref.pop(0)
while ref and not ref[-1]:
    ref.pop()
if out == ref:
    print('   smoke: выдача с тома == эталон redakt.out (%d строк)' % len(out))
    raise SystemExit(0)
print('   smoke: РАСХОЖДЕНИЕ с эталоном (моих строк %d, эталонных %d)'
      % (len(out), len(ref)))
raise SystemExit(1)
PYEOF

# 6) Итог.
after=$(md5f "$volpath")
echo "том после: md5 $after"
echo "ГОТОВО: библиотека связки записана на том $VOL, зона 0o$ZONE"
echo "        запуск редактора:  лен $LU($VOL)^ / *perso:$LU$ZONE / *call redakt"
if [ "$SMOKE" = ok ]; then
    echo "        smoke-проверка пройдена"
else
    echo "        ВНИМАНИЕ: smoke-проверка НЕ пройдена - см. журнал выше" >&2
    exit 1
fi
