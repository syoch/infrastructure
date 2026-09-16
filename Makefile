.PHONY: help install-deps install-hooks test test-backend test-e2e test-e2e-ui test-seed test-obtainium test-obtainium-smoke typecheck clean

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
	@echo "  make typecheck             - Run svelte-check (frontend) and mypy (backend)"
	@echo "  make clean                 - Remove test artifacts (SQLite databases, uploads)"

typecheck:
	cd frontend && npm run typecheck
	mypy backend device_agent

install-hooks:
	git config core.hooksPath .githooks
	@echo "core.hooksPath set to .githooks"

install-deps:
	cd tests && npm install

test-seed:
	python3 backend/manage.py --config tests/config.test.json restore --in tests/bootstrap/seed_backup.tar.gz

test-backend:
	@echo "Running backend tests..."
	python3 tests/backend/test_backup_restore.py
	python3 tests/backend/verify_roundtrip.py
	python3 tests/backend/test_obtainium_compiler.py
	python3 tests/backend/test_control_plane.py
	python3 tests/backend/test_control_plane_core.py
	python3 tests/backend/test_control_plane_backup.py
	python3 tests/backend/test_control_plane_ws.py
	python3 tests/backend/test_app_portal.py
	python3 tests/backend/test_opencode_tool.py
	python3 tests/backend/test_app_portal_delivery_e2e.py
	python3 tests/backend/test_device_agent.py

test-e2e: tests/node_modules
	@echo "Building frontend..."
	cd frontend && npm install && npm run build
	@echo "Running Playwright E2E tests..."
	cd tests && npx playwright test

test-e2e-ui: tests/node_modules
	@echo "Running Playwright E2E tests in UI mode..."
	cd tests && npx playwright test --ui

test: test-backend test-e2e

test-obtainium:
	@if [[ -z "$(BACKUP)" ]]; then \
		echo "Usage: make test-obtainium BACKUP=path/to/backup-XXXX.tgz" >&2; \
		exit 2; \
	fi
	nix develop -c ./tests/obtainium-integration/obtainium-integration --backup-tarball "$(BACKUP)"

test-obtainium-smoke:
	@if [[ -z "$(BACKUP)" ]]; then \
		echo "Usage: make test-obtainium-smoke BACKUP=path/to/backup-XXXX.tgz" >&2; \
		exit 2; \
	fi
	nix develop -c ./tests/obtainium-integration/obtainium-integration \
		--backup-tarball "$(BACKUP)" \
		--apps 3 \
		--output-dir ./tests/obtainium-integration/results/smoke-$$(date +%s)

tests/node_modules: tests/package.json
	cd tests && npm install
	touch tests/node_modules

clean:
	rm -f tests/portal_test.db*
	rm -rf tests/uploads/*
	rm -rf tests/test-results
	rm -rf tests/obtainium-integration/results/*
