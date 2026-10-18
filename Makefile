# SIPROD reverse engineering: generated artifacts and tests.
#
#   make            DTRAN listings of all library modules + loader maps
#   make dtran      <module>.dtran for every dtr/<module>.dtr (dubna, siprod.bin)
#   make loadmaps   tests/siprod/loadmap-{dispak,dubna}.txt
#   make test       regression cases, wiki corpus
#   make coverage   labels of static modules no regression case executes
#   make clean      remove generated DTRAN listings
#
# Needs dubna and dispak on PATH; the corpus test needs the besm6.github.io
# wiki (WIKI=...), and is skipped if it is absent.

WIKI ?= $(HOME)/git/besm6.github.io/wiki
PYTHON ?= python3

# Every module has a DTRAN directive file dtr/<name>.dtr; '*' and '/' in library
# names are spelled '#' and '_' in file names (*W24* -> #W24#).
# The .dtr directive language is described in
# https://github.com/besm6/besm6.github.io/blob/master/wiki/Dtran-instr.md
HASH := \#
DTR := $(wildcard dtr/*.dtr)
DTRAN := $(patsubst dtr/%.dtr,%.dtran,$(DTR))

.DELETE_ON_ERROR:

.PHONY: all dtran loadmaps test regress corpus coverage clean

all: dtran loadmaps

dtran: $(DTRAN)

%.dtran: dtr/%.dtr siprod.bin dtran-siprod.sh
	./dtran-siprod.sh '$(subst _,/,$(subst $(HASH),*,$*))' 2>/dev/null
	test -s '$@'

loadmaps: tests/siprod/loadmap-dispak.txt

tests/siprod/loadmap-dispak.txt: tests/siprod/loadmap.sh tests/siprod/run.sh siprod.bin
	tests/siprod/loadmap.sh

test: regress corpus

regress:
	tests/siprod/run_all.sh

corpus:
	@if [ -d '$(WIKI)' ]; then tests/siprod/corpus.sh '$(WIKI)'; \
	else echo "corpus: $(WIKI) not found, skipped"; fi

coverage:
	$(PYTHON) tools/siprod_labels.py

clean:
	rm -f $(foreach f,$(DTRAN),'$(f)')
