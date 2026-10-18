#!/bin/sh
# Run SIPROD (personal library 67/2702 on disk 2248) on an input text under
# the dispak emulator and print only SIPROD's printer output.
#
# Usage: tests/siprod/run.sh [-r] [-m] [-t] [-C COVFILE] INPUT
#   INPUT   file with SIPROD input (everything after *EXECUTE,
#           e.g. "*RED" ... "*E" "*END")
#   -r      raw: print the whole dispak output (banner, loader messages, end)
#   -m      drop "*no lo" so the loader prints the load map (implies -r)
#   -t      trace extracodes (dispak -t) to stderr
#   -C F    write dispak PC coverage map to F (see tools/siprod_cov.py)
set -eu
usage() { sed -n '2,12s/^# \{0,1\}//p' "$0" >&2; exit 2; }
raw=0 nolo='*no lo' opts=
while getopts rmtC: o; do
    case $o in
    r) raw=1 ;;
    m) raw=1; nolo= ;;
    t) opts="$opts -t" ;;
    C) case $OPTARG in /*) c=$OPTARG ;; *) c=$(pwd)/$OPTARG ;; esac
       opts="$opts --coverage=$c" ;;
    *) usage ;;
    esac
done
shift $((OPTIND - 1))
[ $# -eq 1 ] || usage

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
{
    echo 'ШИФР 419900ЗС5^ОЗУ 32^ТРА 100^АЦП 64^ЛЕН 67(2248)^ЕЕВ1А3'
    echo '*name'
    [ -n "$nolo" ] && echo "$nolo"
    echo '*perso:672702'
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
