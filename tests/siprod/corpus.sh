#!/bin/sh
# Format every SIPROD document of the besm6.github.io wiki (files starting with
# *RED) and check that each run reaches the end of job without a SIPROD error
# or a machine fault.
# Usage: tests/siprod/corpus.sh [WIKIDIR [OUTDIR]]
#   WIKIDIR  default ~/git/besm6.github.io/wiki
#   OUTDIR   keep the raw printouts there (default: a temporary directory)
set -u
D=$(cd "$(dirname "$0")" && pwd)
W=${1:-$HOME/git/besm6.github.io/wiki}
out=${2:-}
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
[ -n "$out" ] && mkdir -p "$out" || out=$work
fail=0
for f in "$W"/*.txt; do
    head -1 "$f" | sed '1s/^\xef\xbb\xbf//' | grep -q '^\*RED' || continue
    b=$(basename "$f" .txt)
    # strip BOM, CR and trailing blanks; *END FILE is added by run.sh
    sed -e '1s/^\xef\xbb\xbf//' -e 's/\r$//' -e 's/ *$//' "$f" |
        grep -v '^\*END F' > "$work/$b.in"
    "$D/run.sh" -r "$work/$b.in" > "$out/$b.out"
    if grep -q 'Е R R О R' "$out/$b.out" || grep -q '^ КОНТРОЛЬ КОМАНДЫ' "$out/$b.out" ||
            ! grep -q 'КОНЕЦ ЗАДАЧИ' "$out/$b.out"; then
        echo "FAIL $b"; fail=1
    else
        echo "ok   $b ($(grep -c 'I *- *[0-9]* -\|^ *- *[0-9]* -' "$out/$b.out") page headers)"
    fi
done
exit $fail
