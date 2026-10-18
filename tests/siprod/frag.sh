#!/bin/sh
# Format a few *RED lines with SIPROD and show the non-empty output lines
# under a column ruler (columns counted from 1).
#
# Usage: tests/siprod/frag.sh [-a] LINE...
#   each LINE is one input card of the *RED text ("*RED" and "*E"/"*END" are
#   added); -a shows all output lines, including empty ones
set -eu
all=0
[ "${1:-}" = -a ] && { all=1; shift; }
D=$(dirname "$0")
echo '         1         2         3         4         5         6         7         8         9         0'
echo '1234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890'
{ echo '*RED'; printf '%s\n' "$@"; echo '*E'; echo '*END'; } | "$D/run.sh" - |
    if [ $all = 1 ]; then cat; else grep -v '^[ I]*$' | grep -v '^\.--*\.$' || true; fi
