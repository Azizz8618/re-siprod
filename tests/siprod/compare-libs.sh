#!/bin/sh
# Compare the SIPROD library on disk 2248 (siprod.bin, zones 2702-2731) with
# the copy on disk 2048 (*LIBRARY:20, zones 1267-1310, dated 20.09.83).
# Every module named in dtr/ is detranslated from both images without
# directives, into build/lib2248/ and build/lib2048/, and a summary is printed:
#   same / differs (number of differing lines) / only in 2248 / only in 2048
# Usage: tests/siprod/compare-libs.sh       (needs besmtool and dubna)
set -u
# besmtool takes decimal zone numbers: 695 = 01267, 18 zones = 01267..01310
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
B=build
mkdir -p $B/lib2248 $B/lib2048
[ -s $B/lib2048/lib.bin ] ||
    besmtool dump 2048 --start=695 --length=18 --to-file=$B/lib2048/lib.bin >/dev/null
for f in dtr/*.dtr; do
    fn=$(basename "$f" .dtr)
    name=$(echo "$fn" | tr '#_' '*/')
    for v in 2248 2048; do
        lib=siprod.bin; [ $v = 2048 ] && lib=$B/lib2048/lib.bin
        [ -s $B/lib$v/"$fn".dtran ] || [ -s $B/lib$v/"$fn".err ] ||
            DTRAN_LIB=$lib DTRAN_OUT=$B/lib$v DTRAN_HINTS= ./dtran-siprod.sh "$name" 2>/dev/null
    done
    a=$B/lib2248/"$fn".dtran b=$B/lib2048/"$fn".dtran
    if [ -s "$a" ] && [ -s "$b" ]; then
        # the header line carries no version information; compare the rest
        n=$(diff "$a" "$b" | grep -c '^[<>]')
        [ "$n" = 0 ] && echo "same     $name" || echo "differs  $name ($n lines)"
    elif [ -s "$a" ]; then
        echo "only2248 $name"
    else
        echo "only2048 $name"
    fi
done
