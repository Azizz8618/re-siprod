#!/bin/sh
# Запись РЕДАКТОРА *RED СИПРОД-П (РЕДÀКТ; режим *DRK встроен) и транслятора
# схем ДРАКОН (DRАКОН) на том 2348, зона 2150(8) - ТОЛЬКО модули редактора,
# без библиотеки компилятора Паскаля.
#
# ПОЧЕМУ ПРЕЖНИЙ СПОСОБ ПИСАЛ ВСЮ БИБЛИОТЕКУ 2570 (исправлено 08.11.2026):
#   колода загружала PERSO-библиотеку компилятора (*perso:402570) во
#   временный каталог задачи; карта *to perso пишет ВЕСЬ временный каталог,
#   поэтому вместе с РЕДÀКТ/DRАКОН в зону 2150 попадали PASCOMPL и все
#   модули run-time (0o126 зон вместо 0o24).  Загрузка 2570 для компиляции
#   и не нужна: карта *call *pascal без *stand запускает штатный системный
#   компилятор 15.0 из постоянной библиотеки (без *stand монитор игнорирует
#   PASCOMPL из временного каталога).  Собранный этим компилятором редактор
#   совпадает с оригинальным СИПРОДом по всем 16 эталонам red-*
#   (подробности и опыты - в ЗАПИСЬ-2150.md).
#
# Метод:
#   задача Монитора-80 монтирует том с правом записи (лен 40(2348-wr)^),
#   штатно транслирует redakt.pas и drakon.pas (*call *pascal) и записывает
#   временный каталог задачи на том (*to perso:402150^).  Временный каталог
#   содержит только что скомпилированные модули, поэтому монитором печатается
#   «ДЛИНА LIBRARY 024 ЗОН» (октально, включая 2 зонных каталога).
#
# После записи редактор запускается с тома вместе с библиотекой Паскаля
# (run-time), как в прогнать-с-тома.sh:
#
#   лен 40(2348)^
#   *perso:402150
#   *perso:402570,cont
#   *call redakt
#   <текст режима *RED>
#
# Этапы:
#   1) резерв тома рядом с ним (<том>.bak-pascal-<дата>, идемпотентно);
#   2) предпроверка зоны 0o2150: свободна либо занята нашей же библиотекой
#      (перезапись); чужие данные - СТОП;
#   3) предпроверка источника run-time: в зоне 0o2570 должен быть PASCOMPL
#      (нужен для smoke-прогона; на саму запись не влияет);
#   4) колода: исходники к ГОСТ-10859 (верхний регистр, Ё->Е), трансляция
#      обоих источников штатным компилятором, *to perso:402150; контроль
#      «ДЛИНА LIBRARY» - библиотека обязана уложиться до зоны 0o2300;
#   5) контроль: каталог зоны 0o2150 содержит RЕДÀКТ и DRАКОН и НЕ содержит
#      PASCOMPL (вся соль исправления); хвост прежней библиотеки за новой
#      длиной стирается свободным паттерном; занятые зоны вне области
#      записи не изменились (против резерва);
#   6) smoke: редактор запускается С ТОМА (*perso:402150 + *perso:402570,cont
#      + *call redakt) на demo/demo1-текст.txt; выдача побайтно равна
#      redakt.out;
#   7) md5 до/после (штамп монитора в шапках зон меняется между
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
ZONE=2150          # восьмеричная зона библиотеки редактора на томе
RT=2570            # PERSO-библиотека Паскаля (источник run-time, только чтение)
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
    if [ -f "$d/$VOL" ]; then
        printf '%s\n' "$d/$VOL"
        break
    fi
done)
[ -n "${volpath:-}" ] || { echo "СТОП: том $VOL не найден в BESM6_PATH" >&2; exit 1; }
echo "том: $volpath"
for t in "$DISPAK" "$BESMTOOL"; do
    command -v "$t" >/dev/null || { echo "СТОП: нет $t в PATH" >&2; exit 1; }
done
command -v python3 >/dev/null || { echo "СТОП: нет python3 в PATH" >&2; exit 1; }
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

# 3) Предпроверка источника run-time (нужен только для smoke).
rtok=0
if "$BESMTOOL" view "$VOL" --start=$(oct $RT) --length=1 --encoding=t 2>/dev/null \
        | grep -q 'СОМРL'; then
    rtok=1
    echo "run-time: библиотека 0o$RT на месте (РАSСОМРL есть)"
else
    echo "ВНИМАНИЕ: в зоне 0o$RT нет РАSСОМРL - smoke-прогон будет пропущен;" >&2
    echo "          редактору при запуске нужна библиотека Паскаля (*perso:40$RT,cont)" >&2
fi

# 4) Колода: трансляция двух источников штатным компилятором и запись
#    каталога задачи.  Карты *perso:402570 и *stand НЕ ставятся: именно
#    *perso:402570 вызывала дозапись всей библиотеки 2570 (см. шапку).
W=$(mktemp -d)
trap 'rm -rf "$W"' EXIT
{
    echo "user 419900 зс5^"
    echo "лен $LU($VOL-wr)^"
    echo "ЕЕВ1А3"
    echo "*name"
    echo "*call yesmemory"
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

# 5) Контроль каталога: редактор на месте, компилятора быть не должно.
v2150=$("$BESMTOOL" view "$VOL" --start=$ZDEC --length=2 --encoding=t 2>/dev/null || true)
if printf '%s\n' "$v2150" | grep -q 'ЕDАК' \
   && printf '%s\n' "$v2150" | grep -q 'АКОN' \
   && ! printf '%s\n' "$v2150" | grep -q 'СОМРL'; then
    echo "каталог зоны 0o$ZONE: RЕДÀКТ и DRАКОН на месте, PASCOMPL не записан"
else
    echo "СТОП: в каталоге зоны 0o$ZONE не то, что ожидалось" \
         "(нужны RЕДÀКТ и DRАКОН, лишним - PASCOMPL):" >&2
    printf '%s\n' "$v2150" | head -5 >&2
    exit 1
fi

# Стирание хвоста прежней библиотеки за новой длиной и контроль
# неизменности тома - на стороне python (формат зоны: 8256 байт =
# 64-байтовая шапка + 1024 слова по 8 байт; логическая зона = файл-зона - 4).
python3 - "$volpath" "$BAK" "$ZDEC" "$DL" <<'PYEOF'
import sys
Z = 8256
vol, bak, z0, n = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
def zones(p):
    return open(p, 'rb').read()
v, b = zones(vol), zones(bak)
def isfree(z):   # свободная зона: 4 нулевых байта и сигнатура 80c7 f105
    return z[0:4] == b'\0\0\0\0' and z[10:14] == b'\x80\xc7\xf1\x05'
F0 = z0 + 4                       # файл-зона начала библиотеки
# протяжённость ПРЕЖНЕЙ библиотеки в резерве (подряд занятые зоны от F0)
old_end = F0
if not isfree(b[Z*F0:Z*(F0+1)]):
    fz = F0
    while fz < len(b) // Z and not isfree(b[Z*fz:Z*(fz+1)]):
        fz += 1
    old_end = fz                  # первая свободная за прежней библиотекой
new_end = F0 + n
# шаблон свободной зоны - из ближайшей свободной зоны резерва за old_end
tmpl = bytes(b[Z*old_end:Z*old_end+64]) if old_end < len(b) // Z \
       and isfree(b[Z*old_end:Z*(old_end+1)]) else b'\0'*64
free = tmpl + b'\0' * (Z - 64)
f = open(vol, 'r+b')
for fz in range(new_end, old_end):    # хвост прежней библиотеки
    f.seek(Z * fz)
    f.write(free)
f.seek(0)
v = f.read()
# контроль: вне [F0, old_end) том равен резерву (либо обе зоны свободны)
bad = []
for fz in range(4, len(v) // Z):
    if F0 <= fz < old_end:
        continue
    a, c = v[Z*fz:Z*(fz+1)], b[Z*fz:Z*(fz+1)]
    if a != c and not (isfree(a) and isfree(c)):
        bad.append('%o' % (fz - 4))
f.close()
if bad:
    raise SystemExit('КРИТИЧНО: изменённые занятые зоны вне записи: %s' % bad[:8])
print('   хвост прежней библиотеки за 0o%04o стёрт (%d зон);' % (old_end - 5, max(0, old_end - new_end)))
print('   вне области записи занятые зоны не изменены: OK')
PYEOF

# 6) Smoke: редактор запускается С ТОМА вместе с run-time из 0o2570,
#    выдача равна эталону.
if [ "$rtok" -eq 1 ]; then
gost "$HERE/$DEMO" > "$W/demo.gost"
{
    echo "user 419999 зс5^"
    echo "лен $LU($VOL)^"
    echo "ЕЕВ1А3"
    echo "*name"
    echo "*call yesmemory"
    echo "*perso:$LU$ZONE"
    echo "*perso:$LU$RT,cont"
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
# выдача начинается после эха карты *call (последней *-карты) и кончается
# КОНЕЦ ЗАДАЧИ; строка-прогон \x0c значима
end = next((i for i, l in enumerate(log) if 'КОНЕЦ ЗАДАЧИ' in l), None)
if end is None:
    print('   smoke: в журнале нет КОНЕЦ ЗАДАЧИ; начало журнала:')
    for l in log[:6]:
        print('     |', l)
    raise SystemExit(1)
stars = [i for i in range(end) if log[i].lstrip().startswith('*')]
if not stars:
    raise SystemExit(1)
call = max(stars)
out = []
for l in log[call+1:end]:
    s = l if l == chr(12) else l.rstrip()
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
for a, b in zip(out, ref):
    if a != b:
        print('     моя :', repr(a[:72]))
        print('     эталон:', repr(b[:72]))
        break
raise SystemExit(1)
PYEOF
else
    SMOKE=пропущен
fi

# 7) Итог.
after=$(md5f "$volpath")
echo "том после: md5 $after"
echo "ГОТОВО: редактор записан на том $VOL, зона 0o$ZONE (только РЕДÀКТ и DRАКОН)"
echo "        запуск:  лен $LU($VOL)^ / *perso:$LU$ZONE / *perso:$LU$RT,cont / *call redakt"
case "$SMOKE" in
    ok)        echo "        smoke-проверка пройдена" ;;
    пропущен)  echo "        smoke-проверка пропущена (нет run-time в 0o$RT)" ;;
    *)         echo "        ВНИМАНИЕ: smoke-проверка НЕ пройдена - см. журнал выше" >&2
               exit 1 ;;
esac
