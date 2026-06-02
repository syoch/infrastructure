.PHONY: help install-deps install-hooks test test-backend test-e2e test-e2e-ui test-seed test-obtainium test-obtainium-smoke clean

help:
	@echo "Available commands:"
	@echo "  make install-deps          - Install frontend test dependencies (Playwright)"
	@echo "  make install-hooks         - Enable .githooks/pre-commit (secret scanner)"
	@echo "  make test                  - Run all backend and E2E tests"
	@echo "  make test-backend          - Run Python backend tests"
	@echo "  make test-e2e              - Run Playwright E2E tests in headless mode"
	@echo "  make test-e2e-ui           - Run Playwright E2E tests in interactive UI mode"
	@echo "  make test-seed             - Reset and seed the local test database"
	@echo "  make test-obtainium        - Run Obtainium integration test (BACKUP=path/to/backup.tgz, on-demand)"
	@echo "  make test-obtainium-smoke  - Run Obtainium integration test on first 3 apps (BACKUP=...)"
	@echo "  make clean                 - Remove test artifacts (SQLite databases, uploads)"

install-hooks:
	git config core.hooksPath .githooks
	@echo "core.hooksPath set to .githooks"

install-deps:
	cd portal/tests && npm install

test-seed:
	python3 portal/manage.py --config portal/tests/config.test.json restore --in portal/tests/bootstrap/seed_backup.tar.gz

test-backend:
	@echo "Running backend tests..."
	python3 portal/tests/backend/test_backup_restore.py
	python3 portal/tests/backend/verify_roundtrip.py

test-e2e: portal/tests/node_modules
	@echo "Running Playwright E2E tests..."
	cd portal/tests && npx playwright test

test-e2e-ui: portal/tests/node_modules
	@echo "Running Playwright E2E tests in UI mode..."
	cd portal/tests && npx playwright test --ui

test: test-backend test-e2e

test-obtainium:
	@if [[ -z "$(BACKUP)" ]]; then \
		echo "Usage: make test-obtainium BACKUP=path/to/backup-XXXX.tgz" >&2; \
		exit 2; \
	fi
	nix develop -c ./portal/tests/obtainium-integration/obtainium-integration --backup-tarball "$(BACKUP)"

test-obtainium-smoke:
	@if [[ -z "$(BACKUP)" ]]; then \
		echo "Usage: make test-obtainium-smoke BACKUP=path/to/backup-XXXX.tgz" >&2; \
		exit 2; \
	fi
	nix develop -c ./portal/tests/obtainium-integration/obtainium-integration \
		--backup-tarball "$(BACKUP)" \
		--apps 3 \
		--output-dir ./portal/tests/obtainium-integration/results/smoke-$$(date +%s)

portal/tests/node_modules: portal/tests/package.json
	cd portal/tests && npm install
	touch portal/tests/node_modules

clean:
	rm -f portal/tests/portal_test.db*
	rm -rf portal/tests/uploads/*
	rm -rf portal/tests/test-results
	rm -rf portal/tests/obtainium-integration/results/*
