# SIPROD reverse engineering: generated artifacts and tests.
#
#   make            DTRAN listings of all library modules + loader maps
#   make dtran      <module>.dtran for every <module>.dtr (dubna, siprod.bin)
#   make loadmaps   tests/siprod/loadmap-{dispak,dubna}.txt
#   make recover    refresh build/ and recovered/ (decompiler, re-runs DTRAN)
#   make test       unit tests, regression cases, wiki corpus
#   make coverage   labels of static modules no regression case executes
#   make clean      remove generated DTRAN listings
#
# Needs dubna and dispak on PATH; the corpus test needs the besm6.github.io
# wiki (WIKI=...), and is skipped if it is absent.

WIKI ?= $(HOME)/git/besm6.github.io/wiki
PYTHON ?= python3

# Every module has a DTRAN directive file <name>.dtr; '*' and '/' in library
# names are spelled '#' and '_' in file names (*W24* -> #W24#).
HASH := \#
NONMODULES := EXPR.dtr TEST.dtr TEST2.dtr schema.dtr
DTR := $(filter-out $(NONMODULES),$(wildcard *.dtr))
DTRAN := $(DTR:.dtr=.dtran)

.DELETE_ON_ERROR:

.PHONY: all dtran loadmaps recover test unit regress corpus coverage clean

all: dtran loadmaps

dtran: $(DTRAN)

%.dtran: %.dtr siprod.bin dtran-siprod.sh
	./dtran-siprod.sh '$(subst _,/,$(subst $(HASH),*,$*))' 2>/dev/null
	test -s '$@'

loadmaps: tests/siprod/loadmap-dispak.txt

tests/siprod/loadmap-dispak.txt: tests/siprod/loadmap.sh tests/siprod/run.sh siprod.bin
	tests/siprod/loadmap.sh

recover:
	./refresh-siprod.sh

test: unit regress corpus

unit:
	$(PYTHON) -m pytest -q tests

regress:
	tests/siprod/run_all.sh

corpus:
	@if [ -d '$(WIKI)' ]; then tests/siprod/corpus.sh '$(WIKI)'; \
	else echo "corpus: $(WIKI) not found, skipped"; fi

coverage:
	$(PYTHON) tools/siprod_labels.py

clean:
	rm -f $(foreach f,$(DTRAN),'$(f)')
