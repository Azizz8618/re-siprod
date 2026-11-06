#!/bin/sh
# Догон боевого тома 2348 до рабочего состояния re-siprod (мониторная запись).
#
# Метод - «мониторный путь» (как в besm-crypto work/*.py):
#   задача Монитора-80 монтирует боевой том с правом записи (dis 41(2348-wr)),
#   читает исходный СИПРОД с диска 2048 (*perso:401267, ЛУ 40) и штатно
#   записывает его в боевой том (*to perso:411267, ЛУ 41).
#
# СВОБОДА ОТ sudo: /usr/local/share/besm6/2348 принадлежит пользователю
# (azizz:azizz, 644); запись в СУЩЕСТВУЮЩИЙ файл прав не требует - sudo
# нужен был бы только на создание/удаление файлов в каталоге (root:root).
# Поэтому резерв снимается обычным cp, а dispak пишет прямо в боевой том.
#
# Этапы:
#   1) резерв боевого в ~/.besm6/2348.bak-prod-sip1267-<дата>;
#   2) мониторная запись СИПРОДа 0o1267 из 2048 ПРЯМО В БОЕВОЙ том;
#   3) дозапись хвостовых 7 зон 0o1311..0o1317 байт-в-байт из рабочего тома
#      (~/.besm6/2348, паттерн свободной зоны 0o52; прецедент besm-crypto
#      CLEANUP-2026-11-01); монитор пишет только 18 зон библиотеки, хвост
#      не трогает;
#   4) контроль:
#      - вне области записи (зоны 0..698, 724..3999) том не изменён
#        (против резерва);
#      - 18 зон библиотеки против 2048: 16 из 18 слово-в-слово; в зонах
#        0o1267/0o1270 монитор переписывает каталог (дата записи) - это
#        штатно;
#      - smoke: СИПРОД из боевого тома (*perso:671267) выдаёт точный
#        эталон tests/siprod/cases/err-10.out;
#   5) md5 до/после (штамп монитора).
#
# Штамп монитора: 2 байта шапки каждой записанной зоны (смещения 3 и 35)
# меняются между сессиями записи - поэтому md5 результата НЕ фиксирован,
# сценарий печатает его до/после. Повторный прогон безопасен: обновляет
# штампы и затем перепроверяет те же инварианты.
#
# Запуск:  sh tools/catchup2348_monitor.sh
set -eu

U=${HOME:-/home/azizz}
PROD=/usr/local/share/besm6/2348
WORK=$U/.besm6/2348
SRC2048=/usr/local/share/besm6/2048
SHARE=/usr/local/share/besm6
DISPAK=$U/Yandex.Disk/dispak/build/dispak/dispak
CASES=$U/Yandex.Disk/re-siprod/tests/siprod/cases
TODAY=$(date +%Y%m%d)
BAK=$U/.besm6/2348.bak-prod-sip1267-$TODAY

md5f() { md5sum "$1" | cut -d' ' -f1; }
before=$(md5f "$PROD")
echo "боевой том до: md5 $before"

# 0) Боевой том принадлежит пользователю; проверяем, что у нас права на запись.
[ -w "$PROD" ] || { echo "нет прав на запись: $PROD" >&2; exit 1; }
[ "$(md5f "$WORK")" = "9d95d6b797023ef4cfdcccfeaa3a12ff" ] \
    || { echo "СТОП: рабочий том $WORK не эталон (9d95d6b7...)" >&2; exit 1; }

# 1) Резерв боевого (idempotent).
if [ ! -f "$BAK" ]; then
    cp -p "$PROD" "$BAK"
    echo "резерв: $BAK md5=$(md5f "$BAK")"
else
    echo "резерв уже есть: $BAK md5=$(md5f "$BAK")"
fi

# 2) Мониторная запись СИПРОДа 0o1267 из 2048 прямо в боевой том.
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
{
    printf '%s\n' 'шифр 419999 зс5^'
    printf '%s\n' 'лен 67(2348)^'
    printf '%s\n' 'dis 41(2348-wr)^'
    printf '%s\n' 'лен 40(2048)^'
    printf '%s\n' 'ОЗУ 32^'
    printf '%s\n' 'АЦПУ 64^'
    printf '%s\n' 'ЕЕВ1А3'
    printf '%s\n' '*name' '*call yesmemory' '*perso:401267' '*no list' '*to perso:411267'
    printf '%s\n' '*end file' '``````' 'ЕКОНЕЦ'
} > "$work/job.b6"
BESM6_PATH="$SHARE" "$DISPAK" "$work/job.b6" 2>&1 \
    | grep -e LIВRАRУ -e ДЛИНА -e КОНЕЦ || true

# 3)+4) Контроль и дозапись хвоста - целиком на стороне python:
python3 - "$PROD" "$BAK" "$SRC2048" "$WORK" <<'PYEOF'
import sys
Z = 8256
tgt, bak, src, wk = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
def words(path, F):
    f = open(path, 'rb'); f.seek(Z * F); z = f.read(Z); f.close()
    return [z[64 + 8*m:70 + 8*m] for m in range(1024)]
tf = open(tgt, 'r+b')
bf = open(bak, 'rb')

# 1. вне области записи (0..698, 724..3999) том равен резерву
touch = []
for r0, r1 in ((0, 699), (724, 4000)):
    for F in range(r0, r1):
        tf.seek(Z * F); a = tf.read(Z)
        bf.seek(Z * F); b = bf.read(Z)
        if a != b:
            touch.append(F)
if touch:
    raise SystemExit('КРИТИЧНО: изменённые зоны вне области записи: %s' % touch[:5])
print('   вне области записи том не изменён: OK')

# 2. библиотека 0o1267..0o1310 (файл 699..716) против 2048
bad_zones = []
for F in range(699, 717):
    if words(tgt, F) != words(src, F):
        bad_zones.append(F)
ok = not bad_zones or (set(bad_zones) <= {699, 700})
print('   библиотека 18 зон: совпали %d, слово-различия в %s'
      % (18 - len(bad_zones), [('%o' % (z - 4)) for z in bad_zones] or 'никуда'))
if not ok:
    raise SystemExit('КРИТИЧНО: различия вне каталоговых зон 0o1267/0o1270')

# 3. хвост 0o1311..0o1317 (файл 717..723) байт-в-байт против рабочего
wf = open(wk, 'rb')
for F in range(717, 724):
    wf.seek(Z * F); data = wf.read(Z)
    tf.seek(Z * F); tf.write(data)
    tf.seek(Z * F)
    if tf.read(Z) != data:
        raise SystemExit('КРИТИЧНО: контроль хвоста, файл-зона %d' % F)
print('   хвост 7 зон дописан байт-в-байт из рабочего тома: OK')
tf.close(); bf.close(); wf.close()
PYEOF

# 5) Smoke: СИПРОД из боевого тома, выдача == эталон err-10.out.
{
    printf '%s\n' 'ШИФР 419900ЗС5^ОЗУ 32^ТРА 100^АЦП 64^ЛЕН 67(2348)^ЕЕВ1А3'
    printf '%s\n' '*name' '*no lo' '*perso:671267' '*call yesmemory' '*main schema' '*execute'
    cat "$CASES/err-10.txt"
    printf '%s\n' '*end file' '``````' 'ЕКОНЕЦ'
} > "$work/smoke.b6"
BESM6_PATH="$SHARE" "$DISPAK" "$work/smoke.b6" 2>&1 \
    | sed -e '1,/\*Е[XХ]Е[CС]UТЕ/d' -e '/КОНЕЦ ЗАДАЧИ/,$d' > "$work/smoke.out"
if cmp -s "$work/smoke.out" "$CASES/err-10.out"; then
    echo "   smoke: выдача == эталон err-10.out ($(wc -c < "$work/smoke.out") байт)"
else
    echo "   СТОП: smoke провален, выдача не совпала с эталоном:" >&2
    diff "$CASES/err-10.out" "$work/smoke.out" | head -10 >&2 || true
    exit 1
fi

# Итоговый md5 (штамп монитора в шапках зон меняется между сессиями).
after=$(md5f "$PROD")
echo "боевой том после: md5 $after"
echo "ГОТОВО: боевой том догонён мониторной записью (было $before, стало $after)"
