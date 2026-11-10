#!/bin/sh
# Detranslate one SIPROD library module with DTRAN under dubna.
# Usage: dtran-siprod.sh NAME
# Environment:
#   DTRAN_LIB    library image (default siprod.bin, the copy from disk 2248)
#   DTRAN_OUT    output directory (default build)
#   DTRAN_HINTS  directory with NAME.dtr directive files (default dtr;
#                empty: no directives)
# Writes $DTRAN_OUT/NAME.dtran ('*' and '/' in NAME become '#' and '_'), or
# $DTRAN_OUT/NAME.err with the job if DTRAN produced nothing.
set -u
lib=$(realpath "${DTRAN_LIB:-siprod.bin}")
out=${DTRAN_OUT:-build}
hints=${DTRAN_HINTS-dtr}
fn=`echo "$1" | tr '*/' '#_'`
mkdir -p "$out"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
# dubna looks for *FILE:<name> as <name>.bin in the current directory;
# names are limited to 6 characters
ln -s "$lib" "$work/siprod.bin"
cat << EOF > "$work/job.b6"
*name dtran
*disc:1/local
*file:siprod,67
*libra:23
*call ficmemory
*call setftn:one,long
*call dtran:67($1)
EOF
if [ -n "$hints" ] && [ -f "$hints/$fn.dtr" ]; then
	cat "$hints/$fn.dtr" >> "$work/job.b6"
fi
cat << EOF >> "$work/job.b6"
*edit
*r:1
*ll
*ee
*end file
EOF
(cd "$work" && dubna job.b6) | sed '/,NAME,/,/,END,/!d' > "$out/$fn.dtran"
if [ -s "$out/$fn.dtran" ]; then
	rm -f "$out/$fn.err"
else
	cp "$work/job.b6" "$out/$fn.err"
	exit 1
fi
