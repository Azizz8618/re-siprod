# SIPROD reverse engineering: generated artifacts and tests.
#
#   make            DTRAN listings of all library modules + loader maps
#   make dtran      build/<module>.dtran for every dtr/<module>.dtr (dubna, siprod.bin)
#   make dis        dis/<module>.asm - BESM-6 autocode of every module (disbesm6)
#   make be         src/<module>.be - the same in BESM-6 source form with
#                   comments (rules of re-dispak)
#   make check      round-trip check: disassemble + assemble == original words
#   make loadmaps   tests/siprod/loadmap-{dispak,dubna}.txt
#   make test       regression cases, wiki corpus
#   make test-perso SIPROD run from a re-recorded PERSO library
#   make coverage   labels of static modules no regression case executes
#   make clean      remove build/
#
# Needs dubna and dispak on PATH; the corpus test needs the besm6.github.io
# wiki (WIKI=...), and is skipped if it is absent.  The disassembly needs
# disbesm6; recording a library into PERSO needs besmtool.

WIKI ?= $(HOME)/git/besm6.github.io/wiki
PYTHON ?= python3
DISBESM6 ?= disbesm6
ZONE ?= 3900

# Every module has a DTRAN directive file dtr/<name>.dtr; '*' and '/' in library
# names are spelled '#' and '_' in file names (*W24* -> #W24#).
# The .dtr directive language is described in
# https://github.com/besm6/besm6.github.io/blob/master/wiki/Dtran-instr.md
HASH := \#
DTR := $(wildcard dtr/*.dtr)
DTRAN := $(patsubst dtr/%.dtr,build/%.dtran,$(DTR))

.PHONY: all dtran dis be check loadmaps test regress corpus test-perso coverage clean

all: dis be loadmaps

dtran: $(DTRAN)

build/%.dtran: dtr/%.dtr siprod.bin dtran-siprod.sh
	./dtran-siprod.sh '$(subst _,/,$(subst $(HASH),*,$*))' 2>/dev/null
	test -s '$@'

# BESM-6 autocode of every module of the library (disbesm6)
dis:
	$(PYTHON) tools/siprod_dis.py

# the same in BESM-6 source form with comments (rules of re-dispak)
be:
	$(PYTHON) tools/siprod_be.py

# the disassembly must be exact: decode + encode == original words
check:
	$(PYTHON) tools/siprod_asm.py

loadmaps: tests/siprod/loadmap-dispak.txt

tests/siprod/loadmap-dispak.txt: tests/siprod/loadmap.sh tests/siprod/run.sh siprod.bin
	tests/siprod/loadmap.sh

test: regress corpus

regress:
	tests/siprod/run_all.sh

corpus:
	@if [ -d '$(WIKI)' ]; then tests/siprod/corpus.sh '$(WIKI)'; \
	else echo "corpus: $(WIKI) not found, skipped"; fi

# SIPROD started from a PERSO library recorded by tools/siprod_perso.py
test-perso:
	ZONE=$(ZONE) tests/siprod/perso_test.sh

coverage: dtran
	$(PYTHON) tools/siprod_labels.py

clean:
	rm -rf build
