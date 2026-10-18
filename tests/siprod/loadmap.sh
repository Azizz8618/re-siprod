#!/bin/sh
# Regenerate the loader address maps of SIPROD (SCHEMA + library modules +
# COMMON blocks):
#   tests/siprod/loadmap-dispak.txt  Monitor Dubna under dispak (the one that
#                                    matches run.sh -C coverage files)
#   tests/siprod/loadmap-dubna.txt   Monitor Dubna under the dubna emulator
# The two agree for SIPROD's own modules up to the FORTRAN runtime, which
# differs, so later modules are shifted.  Cyrillic look-alike letters in the
# dispak listing are converted to Latin.
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
D=$ROOT/tests/siprod
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
printf '%s\n' '*RED' '*E' '*END' > "$work/in.txt"
"$D/run.sh" -m "$work/in.txt" |
    sed -n '/\*Е[XХ]Е[CС]UТЕ/,/^\./p' | sed -e '1d' -e '$d' | grep '[0-7]\{5\} *$' |
    sed 'y/АВСЕНКМОРТХУ/ABCEHKMOPTXY/' > "$D/loadmap-dispak.txt"

ln -s "$ROOT/siprod.bin" "$work/siprod.bin"
printf '%s\n' '*name siprod' '*disc:1/local' '*file:siprod,67' '*perso:670000' \
    '*call ficmemory' '*main schema' '*execute' '*RED' '*E' '*END' '*end file' > "$work/job.b6"
(cd "$work" && dubna job.b6) 2>&1 |
    sed -n '/^\*EXECUTE$/,/CBOБOДHO/p' | sed '1,2d' > "$D/loadmap-dubna.txt"
