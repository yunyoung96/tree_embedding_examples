COQPROJECT := _CoqProject
COQFILES := basic.v basic2.v
COQMAKEFILE := Makefile.coq

.PHONY: all clean

all: $(COQMAKEFILE)
	$(MAKE) -f $(COQMAKEFILE)

$(COQMAKEFILE): $(COQPROJECT) $(COQFILES)
	coq_makefile -f $(COQPROJECT) $(COQFILES) -o $(COQMAKEFILE)

clean:
	@if [ -f $(COQMAKEFILE) ]; then $(MAKE) -f $(COQMAKEFILE) clean; fi
	rm -f $(COQMAKEFILE) $(COQMAKEFILE).conf
	rm -f *.vo *.vos *.vok *.glob *.aux .*.aux
