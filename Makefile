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
	cd frontend && npm install

test-seed:
	python3 backend/manage.py --config tests/config.test.json restore --in tests/bootstrap/seed_backup.tar.gz

test-backend:
	@echo "Running backend tests..."
	python3 backend/core/tests/test_backup_restore.py
	python3 backend/core/tests/verify_roundtrip.py
	python3 backend/obtainium/tests/test_export_schema.py
	python3 backend/obtainium/tests/test_obtainium_compiler.py
	python3 backend/control_plane/tests/test_control_plane.py
	python3 backend/control_plane/tests/test_control_plane_core.py
	python3 backend/control_plane/tests/test_control_plane_backup.py
	python3 backend/control_plane/tests/test_control_plane_ws.py
	python3 backend/control_plane/tests/test_device_agent.py
	python3 backend/app_portal/tests/test_app_portal.py
	python3 backend/app_portal/tests/test_opencode_tool.py
	python3 backend/app_portal/tests/test_app_portal_delivery_e2e.py

test-e2e: frontend/node_modules
	@echo "Building frontend..."
	cd frontend && npm install && npm run build
	@echo "Running Playwright E2E tests..."
	cd frontend && npx playwright test

test-e2e-ui: frontend/node_modules
	@echo "Running Playwright E2E tests in UI mode..."
	cd frontend && npx playwright test --ui

test: test-backend test-e2e

test-obtainium:
	@if [[ -z "$(BACKUP)" ]]; then \
		echo "Usage: make test-obtainium BACKUP=path/to/backup-XXXX.tgz" >&2; \
		exit 2; \
	fi
	nix develop -c ./backend/obtainium/tests/avd/obtainium-integration --backup-tarball "$(BACKUP)"

test-obtainium-smoke:
	@if [[ -z "$(BACKUP)" ]]; then \
		echo "Usage: make test-obtainium-smoke BACKUP=path/to/backup-XXXX.tgz" >&2; \
		exit 2; \
	fi
	nix develop -c ./backend/obtainium/tests/avd/obtainium-integration \
		--backup-tarball "$(BACKUP)" \
		--apps 3 \
		--output-dir ./backend/obtainium/tests/avd/results/smoke-$$(date +%s)

frontend/node_modules: frontend/package.json
	cd frontend && npm install
	touch frontend/node_modules

clean:
	rm -f tests/portal_test.db*
	rm -rf tests/uploads/*
	rm -rf tests/test-results
	rm -rf backend/obtainium/tests/avd/results/*
