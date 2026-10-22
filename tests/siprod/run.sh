#!/bin/sh
# Run SIPROD (personal library 67/1267 on disk 2348) on an input text under
# the dispak emulator and print only SIPROD's printer output.
#
# SIPROD is run from disk 2348 ("Monitor-80") by default: the library is
# written into the PERSO area of the working copy of the volume, at zone
# 01267 (octal), which is where the monitor looks for it.  The copy of the
# library that ships with volume 2348 is incomplete (95 of 98 modules, no
# STANDA/STAATP/VIAPUZ), so the full library is written every run.
#
# Usage: tests/siprod/run.sh [-r] [-m] [-t] [-C COVFILE] [-x DISPAKOPT]
#                            [-v VOL] [-z ZONE] [-l LIBRARY] INPUT
#   INPUT   file with SIPROD input (everything after *EXECUTE,
#           e.g. "*RED" ... "*E" "*END")
#   -r      raw: print the whole dispak output (banner, loader messages, end)
#   -m      drop "*no lo" so the loader prints the load map (implies -r)
#   -t      trace extracodes (dispak -t) to stderr
#   -C F    write dispak PC coverage map to F (see tools/siprod_cov.py)
#   -x O    pass option O to dispak (repeatable), e.g. -x --trace-e64
#   -v VOL  volume to run from (default 2348)
#   -z ZONE PERSO zone of the library (default 695 = 01267 octal)
#   -l LIB  library image to write into the PERSO (default siprod.bin)
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
usage() { sed -n '2,20s/^# \{0,1\}//p' "$0" >&2; exit 2; }
raw=0 nolo='*no lo' opts=
VOL=${SIPROD_VOL:-2348}
ZONE=${SIPROD_ZONE:-695}
LIB=${SIPROD_LIB:-$ROOT/siprod.bin}
while getopts rmtC:x:vz:l: o; do
    case $o in
    r) raw=1 ;;
    m) raw=1; nolo= ;;
    t) opts="$opts -t" ;;
    C) case $OPTARG in /*) c=$OPTARG ;; *) c=$(pwd)/$OPTARG ;; esac
       opts="$opts --coverage=$c" ;;
    x) opts="$opts $OPTARG" ;;
    v) VOL=$OPTARG ;;
    z) ZONE=$OPTARG ;;
    l) LIB=$OPTARG ;;
    *) usage ;;
    esac
done
shift $((OPTIND - 1))
[ $# -eq 1 ] || usage

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
cp "/usr/local/share/besm6/$VOL" "$work/$VOL"
BESM6_PATH="$work:/usr/local/share/besm6"
export BESM6_PATH
# библиотека СИПРОДа в ПЕРСО тома
python3 "$ROOT/tools/siprod_perso.py" --vol="$VOL" --zone="$ZONE" \
    --image="$LIB" --work="$work" >/dev/null

# зоны монитора задаются в восьмеричной системе
z=$(printf '%o' "$ZONE")
{
    echo "ШИФР 419900ЗС5^ОЗУ 32^ТРА 100^АЦП 64^ЛЕН 67($VOL)^ЕЕВ1А3"
    echo '*name'
    [ -n "$nolo" ] && echo "$nolo"
    echo "*perso:67$z"
    echo '*call yesmemory'
    echo '*main schema'
    echo '*execute'
    cat "$1"
    echo '*end file'
    echo '``````'
    echo 'ЕКОНЕЦ'
} > "$work/job.b6"

# shellcheck disable=SC2086
(cd "$work" && dispak $opts job.b6) > "$work/out.txt" 2>&1 || true
if [ $raw = 1 ]; then
    cat "$work/out.txt"
else
    # Printer output follows the echoed *EXECUTE card (Latin U is the only
    # non-lookalike letter in it) and precedes the end-of-job message.
    sed -e '1,/\*Е[XХ]Е[CС]UТЕ/d' -e '/^ КОНЕЦ ЗАДАЧИ/,$d' "$work/out.txt"
fi
