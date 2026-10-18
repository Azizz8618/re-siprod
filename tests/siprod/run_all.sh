#!/bin/sh
# Regression set: run every tests/siprod/cases/*.txt through SIPROD (run.sh)
# and compare with the expected output in the matching .out file.
# Usage: tests/siprod/run_all.sh [-u]     (-u: rewrite .out files)
set -u
D=$(cd "$(dirname "$0")" && pwd)
update=0
[ "${1:-}" = -u ] && update=1
fail=0
for t in "$D"/cases/*.txt; do
    exp=${t%.txt}.out
    got=$("$D/run.sh" "$t")
    if [ $update = 1 ]; then
        printf '%s\n' "$got" > "$exp"
    elif printf '%s\n' "$got" | cmp -s - "$exp"; then
        echo "ok   $(basename "$t" .txt)"
    else
        echo "FAIL $(basename "$t" .txt)"
        fail=1
    fi
done
exit $fail
