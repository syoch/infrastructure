.PHONY: help run smoke clean

OI_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
SCRIPT := $(OI_ROOT)/obtainium-integration

help:
	@echo "obtainium-integration Makefile"
	@echo "  make run BACKUP=<path>     - run the full integration test"
	@echo "  make smoke BACKUP=<path>   - run a smoke test (3 apps)"
	@echo "  make clean                 - remove local results"

run:
	@if [[ -z "$(BACKUP)" ]]; then echo "Usage: make run BACKUP=path/to/backup-XXXX.tgz" >&2; exit 2; fi
	$(SCRIPT) --backup-tarball "$(BACKUP)"

smoke:
	@if [[ -z "$(BACKUP)" ]]; then echo "Usage: make smoke BACKUP=path/to/backup-XXXX.tgz" >&2; exit 2; fi
	$(SCRIPT) --backup-tarball "$(BACKUP)" --apps 3 --output-dir $(OI_ROOT)/results/smoke-$(shell date +%s)

clean:
	rm -rf $(OI_ROOT)/results/*
