#!/bin/sh
# Двухфазная запись редактора СИПРОД-П на том 2348, зона 2150(8):
# по умолчанию ТОЛЬКО РЕДÀКТ (транслятор схем ДРАКОН встроен в редактор
# как режим *DRK; вернуть отдельный модуль DRАКОН - пустой TOLKO_REDAKT=),
# без библиотеки компилятора.  Трансляция - именно компилятором
# PASCOMPL 15.1 из зоны 2570(8); библиотека 2570 в зону 2150 НЕ попадает.
#
# ПОЧЕМУ СХЕМА ДВУХФАЗНАЯ.  Карта *perso читает библиотеку ЦЕЛИКОМ во
# временный каталог задачи (LIBDRUM копирует и каталог, и тела модулей),
# а *to perso пишет весь временный каталог: одна колода «*perso:402570 +
# трансляции + *to perso:402150» таскала в зону 2150 все ~100 зон
# библиотеки 2570 (компилятор и весь run-time).  Вычистить временный
# каталог штатно нечем:
#   - приказ Y программы pashelp убирает только имена «P/», «PAS» и TIME;
#     модули 2570 с прочими именами (PRO203, ZAP203, ARFALIB, OBPROG...)
#     остаются;
#   - карта *EXCLUDE - не средство правки каталога: она отвязывает модули
#     от памяти задачи, каталог на диске не трогает, а в системе без
#     работника EXCLUDE (монитор Дубны из dispak) ещё и завершает задание
#     (активный тест LIBDELET 08.11.2026 - ЗАПИСЬ-2150.md, п. 2.3).
#
# СХЕМА (каждое задание - отдельный прогон монитора):
#   фаза 1а: *perso:402570, *stand, *call *pascal <redakt.pas>,
#            *call libsub + карта 402570 (вычитание библиотеки 2570 из
#            временного каталога), *to perso:40<ЧЕРНОВИК_А>
#            -> черновик А: только РЕДÀКТ (наблюдалось 0o16 зон);
#   фаза 1б: то же для drakon.pas -> черновик Б: только DRАКОН (0o11);
#            НЕ выполняется по умолчанию (TOLKO_REDAKT=1): отдельный
#            модуль ДРАКОН на том не записывается;
#   фаза 2:  *perso:40<ЧЕРНОВИК_А> + *perso:40<ЧЕРНОВИК_Б>,cont (слияние
#            в временном каталоге) + *to perso:402150 - каталог и
#            размещение модулей строит сам монитор (0o24 зон).
#   По опытам с LIBSUB (ЗАПИСЬ-2150.md, п. 2.1) в каталоге выживает
#   последний скомпилированный модуль, поэтому программы собираются по
#   одной, а слияние вынесено в отдельное задание.  Черновые зоны после
#   записи стираются сценарием (том возвращается к виду до работы).
#
# Пуск редактора - с тома, run-time из библиотеки Паскаля (том монтируется
# только на чтение):
#
#   лен 40(2348)^
#   *perso:402150
#   *perso:402570,cont
#   *call redakt
#   <текст режима *RED>
#
# Переключатели (переменные окружения):
#   TOLKO_REDAKT=1              - (по умолчанию) собрать и записать
#                                 только редактор; отдельный drakon.pas
#                                 не записывается - транслятор усхем
#                                 встроен в РЕДÀКТ (режим *DRK);
#                                 вернуть DRАКОН: TOLKO_REDAKT=
#   CHERNOVIK_A=5000            - зона черновика А (восьмеричная);
#   CHERNOVIK_B=5100            - зона черновика Б (восьмеричная).
#
# Этапы:
#   1) резерв тома (<том>.bak-pascal-<ГГГГММДД>, идемпотентно);
#   2) предпроверки: в 0o2570 есть РАSСОМРЛ (иначе трансляции не будет);
#      зона 0o2150 свободна либо занята нашей библиотекой (перезапись);
#      черновые зоны свободны;
#   3) три задания: контроль баннера компилятора («15.0 (15.02.82)»
#      запрещён - трансляция обязана идти PASCOMPL 15.1 из 2570),
#      «ДЛИНА LIBRARY» каждого задания не выше 0o30 зон, признаков
#      «ИСПОРЧ» в журналах быть не должно;
#   4) контроль каталога 0o2150: РЕДÀКТ есть (DRАКОН - только при непустой TOLKO_REDAKT), РАSСОМРL и
#      модули «P/» (run-time) отсутствуют;
#   5) стирание хвоста прежней записи за новой длиной и черновых зон
#      свободным паттерном; контроль: вне области записи занятые зоны
#      не изменились (против резерва);
#   6) smoke: редактор запускается С ТОМА (*perso:402150 +
#      *perso:402570,cont + *call redakt) на demo/demo1-текст.txt,
#      выдача побайтно равна redakt.out.
#
# Окружение: DISPAK, BESMTOOL, BESM6_PATH (как в прогнать.sh).  В
# BESM6_PATH, кроме копии тома 2348, должны лежать и системные тома
# Монитора-80 (2048, 2053, 2099) - без них монитор не пускает задачу
# («disk_open: no 2053 image found»).  Том 2348 берётся из ПЕРВОЙ
# найденной копии в BESM6_PATH - держите рабочую копию впереди боевого
# тома.  Первый прогон - на рабочей копии.
#
# Запуск:  sh pascal/scripts/запись-2348.sh
set -eu

DISPAK=${DISPAK:-dispak}
BESMTOOL=${BESMTOOL:-besmtool}
U=${HOME:-/home/azizz}
export BESM6_PATH="${BESM6_PATH:-$HOME/.besm6:/usr/local/share/besm6}"
HERE=$(cd "$(dirname "$0")" && pwd)

VOL=2348
LU=40
ZONE=2150                 # восьмеричная зона библиотеки связки на томе
SRC=2570                  # PERSO-библиотека компилятора (только чтение)
ALIM=30                   # потолок «ДЛИНА LIBRARY» каждого задания (дес.)
CA=${CHERNOVIK_A:-5000}   # зона черновика А (РЕДÀКТ)
CB=${CHERNOVIK_B:-5100}   # зона черновика Б (DRАКОН)
# По умолчанию записывается ТОЛЬКО редактор: транслятор схем ДРАКОН
# встроен в РЕДÀКТ (режим *DRK), отдельный модуль на том не нужен.
# Вернуть DRАКОН в зону можно, задав пустую переменную: TOLKO_REDAKT=
TOLKO_REDAKT=${TOLKO_REDAKT:-1}
export TOLKO_REDAKT
DEMO="$HERE/../demo/demo1-текст.txt"
ETALON="$HERE/../redakt.out"

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
for t in "$DISPAK" python3; do
    command -v "$t" >/dev/null || { echo "СТОП: нет $t в PATH" >&2; exit 1; }
done
for f in "$HERE/../source/redakt.pas" "$DEMO" "$ETALON"; do
    [ -f "$f" ] || { echo "СТОП: нет $f" >&2; exit 1; }
done
if [ -z "${TOLKO_REDAKT:-}" ]; then
    [ -f "$HERE/../source/drakon.pas" ] || { echo "СТОП: нет $HERE/../source/drakon.pas" >&2; exit 1; }
fi
if [ "$CB" -le "$((CA + 40))" ]; then
    echo "СТОП: черновик Б (0o$CB) должен быть минимум на 0o40 зон правее" \
         "черновика А (0o$CA)" >&2
    exit 1
fi

before=$(md5f "$volpath")
echo "том до: md5 $before"

# 1) Резерв (идемпотентно).  Если каталог тома недоступен на запись
#    (боевой том), резерв уходит в ~/.besm6, как требует README re-siprod
#    (2348.bak-<цель>-<ГГГГММДД>).
BAK="$volpath.bak-pascal-$(date +%Y%m%d)"
if [ ! -w "$(dirname "$volpath")" ]; then
    mkdir -p "$U/.besm6"
    BAK="$U/.besm6/2348.bak-pascal-prod-$(date +%Y%m%d)"
fi
if [ ! -f "$BAK" ]; then
    cp -p "$volpath" "$BAK"
    echo "резерв: $BAK md5=$(md5f "$BAK")"
else
    echo "резерв уже есть: $BAK"
fi

# 2) Предпроверки тома (на стороне python: зона = 8256 байт - шапка 64
#    байта + 1024 слова по 8; логическая зона = файл-зона - 4).
python3 - "$volpath" "$ZONE" "$SRC" "$CA" "$CB" <<'PYEOF'
import sys
Z = 8256
vol = sys.argv[1]
z2150, z2570 = int(sys.argv[2], 8), int(sys.argv[3], 8)
ca, cb = int(sys.argv[4], 8), int(sys.argv[5], 8)
data = open(vol, 'rb').read()
nz = len(data) // Z
TEXT = [" ", ".", "Б", "Ц", "Д", "Ф", "Г", "И", "(", ")", "*", "Й",
        "Л", "Я", "Ж", "/", "0", "1", "2", "3", "4", "5", "6", "7",
        "8", "9", "Ь", ",", "П", "-", "+", "Ы", "З", "A", "B", "C",
        "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O",
        "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "Ш",
        "Э", "Щ", "Ч", "Ю"]
def word(z, i):
    off = (z + 4) * Z + 64 + 8 * i
    return int.from_bytes(data[off:off + 8], 'little') & ((1 << 48) - 1)
def txt(w):
    return ''.join(TEXT[(w >> (42 - 6 * i)) & 0x3F] for i in range(8))
def isfree(z):
    # свободная зона двух видов: с сигнатурой в шапке или целиком нулевая
    off = (z + 4) * Z
    h = data[off:off + 64]
    if h[0:4] == b'\0\0\0\0' and h[10:14] == b'\x80\xc7\xf1\x05':
        return True
    return data[off:off + Z] == b'\0' * Z
def catalog_names(z):
    names = []
    for zc in (z, z + 1):
        for i in range(2, 1022, 2):
            w = word(zc, i)
            if w == 0:
                return names
            names.append(txt(w).rstrip())
    return names
def fail(msg):
    sys.exit('СТОП: ' + msg)

# 2а. Компилятор на месте?
if 'PASCOMPL' not in catalog_names(z2570):
    fail('в зоне 0o%o нет РАSСОМРL - трансляция компилятором 2570 '
         'невозможна' % z2570)
print('   зона 0o%o: РАSСОМРЛ на месте' % z2570)

# 2б. Зона связки: свободна либо наша (есть RЕДÀКТ).
n = catalog_names(z2150)
if not n:
    print('   зона 0o%o свободна - записываем' % z2150)
elif any(x.upper().startswith('RED') or x.upper().startswith('РЕД')
         for x in n):
    print('   зона 0o%o занята нашей библиотекой - перезаписываем' % z2150)
else:
    fail('зона 0o%o занята чужими данными (%s...)' % (z2150, n[0]))

# 2в. Черновые зоны: свободны либо заняты НАШИМ незавершённым черновиком
#     (прерванный прогон сценария: в зоне есть наш каталог с РЕДÀКТ или
#     DRАКОН) - тогда полоса занятых зон от файл-зоны (z+4) стирается
#     свободным паттерном; чужие данные - СТОП.
def wipe_strip(z):
    global data
    fz = z + 4
    n = 0
    while fz < len(data) // Z and not isfree(fz):
        n += 1
        fz += 1
    s = bytearray(data)
    hdr = bytearray(Z)
    hdr[10:14] = b'\x80\xc7\xf1\x05'
    for fi in range(z + 4, z + 4 + n):
        s[Z*fi:Z*(fi+1)] = bytes(hdr)
    open(vol, 'wb').write(bytes(s))
    data = bytes(s)
    return n

for nm, z in (('А', ca), ('Б', cb)):
    if not isfree(z):
        n_ = catalog_names(z)
        up_ = [x.upper() for x in n_]
        ours = (any(x.startswith('RED') or x.startswith('РЕД') for x in up_)
                or any(x.startswith('DRA') or x.startswith('ДРА') for x in up_))
        if not ours:
            fail('черновая зона 0o%o занята чужими данными (%s...) - задайте другую '
                 'переменной CHERNOVIK_%s' % (z, up_[0] if up_ else '?', nm))
        w = wipe_strip(z)
        print('   черновик %s: зона 0o%o была занята нашим черновиком - стёрто зон: %d'
              % (nm, z, w))
    else:
        print('   черновик %s: зона 0o%o свободна' % (nm, z))
PYEOF

# 3) Колода фазы 1: трансляция одного исходника компилятором 2570
#    (*perso:402570 + *stand), вычитание библиотеки 2570 из временного
#    каталога (LIBSUB), запись каталога задачи в черновую зону.
W=$(mktemp -d)
trap 'rm -rf "$W"' EXIT

compile_deck() { # $1 имя колоды, $2 исходник, $3 зона черновика
    {
        echo "user 419900 зс5^"
        echo "лен $LU($VOL-wr)^"
        echo "ЕЕВ1А3"
        echo "*name"
        echo "*call yesmemory"
        echo "*perso:$LU$SRC"
        echo "*stand"
        echo "*call *pascal"
        gost "$HERE/../source/$2"
        echo "*call libsub"
        echo "$LU$SRC"
        echo "*to perso:$LU$3"
        echo "*end file"
        echo '``````'
        echo 'ЕКОНЕЦ'
    } > "$W/$1.b6"
}

run_deck() { # $1 имя колоды
    echo "--- прогон $1"
    timeout 1800 "$DISPAK" "$W/$1.b6" > "$W/$1.log" 2>&1 || {
        echo "СТОП: прогон $1 не удался (код $?), журнал: $W/$1.log" >&2
        tail -15 "$W/$1.log" >&2; exit 1; }
    if grep -aq 'СПОРЧ' "$W/$1.log"; then
        echo "СТОП: в журнале $1 есть «ИСПОРЧ...»:" >&2
        grep -a -B1 -A2 'СПОРЧ' "$W/$1.log" | head -12 >&2
        exit 1
    fi
    if grep -aq '15\.0 (15\.02\.82)' "$W/$1.log"; then
        echo "СТОП: $1 - трансляция штатным компилятором 15.0 (15.02.82);" >&2
        echo "      нужен PASCOMPL из зоны 0o$SRC (карты *perso + *stand)" >&2
        exit 1
    fi
    grep -a '1[0-9]\.[0-9]* (' "$W/$1.log" | head -1 || true
    dlina=$(grep -a 'ДЛИНА' "$W/$1.log" | grep -a 'ЗОН' | tail -1 \
            | sed 's/.*[^0-7]\([0-7][0-7]*\)[ \t]*ЗОН.*/\1/')
    case "$dlina" in
        ''|*[!0-7]*) echo "СТОП: $1: не понял «ДЛИНА LIBRARY»: '$dlina'" >&2
                     tail -15 "$W/$1.log" >&2; exit 1 ;;
    esac
    DL=$(oct "$dlina")
    echo "    ДЛИНА LIBRARY $dlina ЗОН ($DL)"
    if [ "$DL" -gt "$ALIM" ]; then
        echo "СТОП: $1: библиотека $DL зон - выше потолка $ALIM;" >&2
        echo "      похоже, вычитание 2570 (LIBSUB) не сработало; журнал:" >&2
        echo "      $W/$1.log" >&2
        exit 1
    fi
    echo "$DL" > "$W/$1.длина"
}

echo '=== ФАЗА 1а: РЕДÀКТ -> черновик 0o'"$CA"
compile_deck deck1-редакт redakt.pas "$CA"
run_deck deck1-редакт

if [ -z "${TOLKO_REDAKT:-}" ]; then
    echo '=== ФАЗА 1б: DRАКОН -> черновик 0o'"$CB"
    compile_deck deck2-дракон drakon.pas "$CB"
    run_deck deck2-дракон
fi

# 4) Колода фазы 2: слияние черновиков и запись в зону 2150.
#    Карты *perso читают черновики в один временный каталог (вторая - с
#    дозаписью, cont), *to perso пишет каталог задачи на том: каталог и
#    размещение модулей строит монитор.
echo '=== ФАЗА 2: слияние черновиков -> зона 0o'"$ZONE"
{
    echo "user 419900 зс5^"
    echo "лен $LU($VOL-wr)^"
    echo "ЕЕВ1А3"
    echo "*name"
    echo "*call yesmemory"
    echo "*perso:$LU$CA"
    if [ -z "${TOLKO_REDAKT:-}" ]; then
        echo "*perso:$LU$CB,cont"
    fi
    echo "*to perso:$LU$ZONE"
    echo "*end file"
    echo '``````'
    echo 'ЕКОНЕЦ'
} > "$W/deck3-слияние.b6"
run_deck deck3-слияние
DL=$(cat "$W/deck3-слияние.длина")

# 5) Контроль каталога 2150, стирание хвостов, контроль тома.
DL1=$(cat "$W/deck1-редакт.длина")
DL2=0
if [ -z "${TOLKO_REDAKT:-}" ]; then
    DL2=$(cat "$W/deck2-дракон.длина")
fi
python3 - "$volpath" "$BAK" "$ZONE" "$DL" "$CA" "$DL1" "$CB" "$DL2" <<'PYEOF'
import os
import sys
TOLKO_REDAKT = bool(os.environ.get('TOLKO_REDAKT'))
Z = 8256
vol, bak = sys.argv[1], sys.argv[2]
z0, n = int(sys.argv[3], 8), int(sys.argv[4])
ca, dl1 = int(sys.argv[5], 8), int(sys.argv[6])
cb, dl2 = int(sys.argv[7], 8), int(sys.argv[8])
raw_v = open(vol, 'rb').read()
raw_b = open(bak, 'rb').read()
TEXT = [" ", ".", "Б", "Ц", "Д", "Ф", "Г", "И", "(", ")", "*", "Й",
        "Л", "Я", "Ж", "/", "0", "1", "2", "3", "4", "5", "6", "7",
        "8", "9", "Ь", ",", "П", "-", "+", "Ы", "З", "A", "B", "C",
        "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O",
        "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "Ш",
        "Э", "Щ", "Ч", "Ю"]
def txt(w):
    return ''.join(TEXT[(w >> (42 - 6 * i)) & 0x3F] for i in range(8))
def zone_words(d, fz):
    off = fz * Z + 64
    ch = d[off:off + 8192]
    return [int.from_bytes(ch[i*8:i*8+8], 'little') & ((1 << 48) - 1)
            for i in range(1024)]
def isfree(d, fz):
    # свободная зона - двух видов: со стандартной сигнатурой в шапке
    # (4 нулевых байта + 80 c7 f1 05) или целиком нулевая
    off = fz * Z
    h = d[off:off + 64]
    if h[0:4] == b'\0\0\0\0' and h[10:14] == b'\x80\xc7\xf1\x05':
        return True
    return d[off:off + Z] == b'\0' * Z
F0 = z0 + 4

# 5а. Каталог зоны связки.
names, info = [], []
w0 = zone_words(raw_v, F0)
for i in range(2, 1022, 2):
    if w0[i] == 0:
        break
    names.append(txt(w0[i]).rstrip())
    info.append(w0[i + 1])
for nm, e in zip(names, info):
    print('   %-9s %012o' % (nm, e))
up = [x.upper() for x in names]
if not any(x.startswith('RED') or x.startswith('РЕД') for x in up):
    raise SystemExit('СТОП: в каталоге 0o%o нет РЕДÀКТ' % z0)
dra = any(x.startswith('DRA') or x.startswith('ДРА') for x in up)
if not dra and not TOLKO_REDAKT:
    raise SystemExit('СТОП: в каталоге 0o%o нет DRАКОН' % z0)
if 'PASCOMPL' in up:
    raise SystemExit('СТОП: в каталоге 0o%o есть РАSСОМРL' % z0)
if any(x.startswith('P/') for x in up):
    raise SystemExit('СТОП: в каталоге 0o%o есть модули P/ (run-time)' % z0)
if TOLKO_REDAKT:
    print('   каталог 0o%o: только РЕДÀКТ на месте (TOLKO_REDAKT), библиотеки 2570 нет' % z0)
else:
    print('   каталог 0o%o: РЕДÀКТ и DRАКОН на месте, библиотеки 2570 нет' % z0)

# 5б. Стирание: хвост прежней записи за новой длиной и черновые зоны.
old_end = F0
if not isfree(raw_b, F0):
    fz = F0
    while fz < len(raw_b) // Z and not isfree(raw_b, fz):
        fz += 1
    old_end = fz
new_end = F0 + n
# шаблон свободной зоны - ЦЕЛАЯ зона из резерва; счётчик в байтах 4/36
# корректируется по номеру зоны (на томе он растёт на 0x10 от зоны к зоне)
tpl, anchor = None, None
for fz in range(old_end, len(raw_b) // Z):
    if isfree(raw_b, fz) and raw_b[Z*fz+10:Z*fz+14] == b'\x80\xc7\xf1\x05':
        tpl = raw_b[Z*fz:Z*fz+Z]        # полная зона - 8256 байт
        anchor = fz
        break
out = bytearray(raw_v)
wiped = 0
def put_free(fz):
    global wiped
    if isfree(out, fz):
        return          # уже свободна - не трогаем
    if tpl is None:
        blk = b'\0' * Z
    else:
        blk = bytearray(tpl)
        blk[4] = (tpl[4] + 0x10 * (fz - anchor)) & 0xFF
        blk[36] = (blk[4] + 0x10) & 0xFF
        blk = bytes(blk)
    assert len(blk) == Z
    out[Z*fz:Z*(fz+1)] = blk
    wiped += 1
for fz in range(new_end, old_end):      # хвост прежней библиотеки
    put_free(fz)
for cz, dln in ((ca, dl1), (cb, dl2)):  # черновые зоны
    if dln <= 0:
        continue            # TOLKO_REDAKT: черновика Б нет
    for fz in range(cz + 4, cz + 4 + dln):
        put_free(fz)
open(vol, 'wb').write(bytes(out))
print('   стёрто свободным паттерном зон: %d (хвост прежней записи и черновики)'
      % wiped)

# 5в. Контроль: вне области записи ([F0, max(old_end,new_end))) том равен
#     резерву; пары «свободная зона - свободная зона» тоже допустимы.
bad = []
for fz in range(4, len(out) // Z):
    if F0 <= fz < max(old_end, new_end):
        continue
    a = bytes(out[Z*fz:Z*(fz+1)])
    c = raw_b[Z*fz:Z*(fz+1)]
    if a != c and not (isfree(out, fz) and isfree(raw_b, fz)):
        bad.append('%o' % (fz - 4))
if bad:
    raise SystemExit('КРИТИЧНО: изменённые занятые зоны вне записи: %s'
                     % bad[:8])
print('   вне области записи занятые зоны не изменены: OK')
PYEOF

# 6) Smoke: редактор запускается С ТОМА, выдача равна эталону.
gost "$DEMO" > "$W/demo.gost"
{
    echo "user 419999 зс5^"
    echo "лен $LU($VOL)^"
    echo "ЕЕВ1А3"
    echo "*name"
    echo "*call yesmemory"
    echo "*perso:$LU$ZONE"
    echo "*perso:$LU$SRC,cont"
    echo "*call redakt"
    cat "$W/demo.gost"
    echo "*end file"
    echo '``````'
    echo 'ЕКОНЕЦ'
} > "$W/smoke.b6"
timeout 600 "$DISPAK" "$W/smoke.b6" > "$W/smoke.log" 2>&1 || true

python3 - "$W/smoke.log" "$ETALON" <<'PYEOF' && SMOKE=ok || SMOKE=нет
import sys
log = open(sys.argv[1], encoding='utf-8').read().split('\n')
perso = next((i for i, l in enumerate(log) if ':402150' in l), None)
if perso is None:
    print('   smoke: в журнале нет карты *perso:402150; начало журнала:')
    for l in log[:6]:
        print('     |', l)
    raise SystemExit(1)
call = next((i for i, l in enumerate(log[perso+1:], perso+1)
             if l.lstrip().startswith('*') and 'LL' in l.replace('Л', 'L')),
            None)
if call is None:
    raise SystemExit(1)
out = []
for l in log[call+1:]:
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
for a, b in zip(out, ref):
    if a != b:
        print('     моя :', repr(a[:72]))
        print('     эталон:', repr(b[:72]))
        break
raise SystemExit(1)
PYEOF

# 7) Итог.
after=$(md5f "$volpath")
echo "том после: md5 $after"
if [ -n "${TOLKO_REDAKT:-}" ]; then
    echo "ГОТОВО: редактор записан на том $VOL, зона 0o$ZONE (только РЕДÀКТ, без библиотеки 2570)"
else
    echo "ГОТОВО: связка редактора записана на том $VOL, зона 0o$ZONE (РЕДÀКТ + DRАКОН, без библиотеки 2570)"
fi
echo "        пуск:  лен $LU($VOL)^ / *perso:$LU$ZONE / *perso:$LU$SRC,cont / *call redakt"
case "$SMOKE" in
    ok) echo "        smoke-проверка пройдена" ;;
    *)  echo "        ВНИМАНИЕ: smoke-проверка НЕ пройдена - см. журнал выше" >&2
        exit 1 ;;
esac
