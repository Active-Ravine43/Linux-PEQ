VENV ?= .venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip
BLACK = $(VENV)/bin/black
ISORT = $(VENV)/bin/isort
PYLINT = $(VENV)/bin/pylint

.PHONY: all venv install run test format format-check lint lint-full clean install-system help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

all: venv install  ## Create venv + install (production + dev)

venv:  ## Create virtualenv
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip

install: venv  ## Install package + dev dependencies
	$(PIP) install -e ".[dev]"

run:  ## Launch the TUI
	$(PYTHON) -m peq_app

test:  ## Run test suite
	$(PYTHON) -m pytest tests/ -v

# ── Code Quality ─────────────────────────────────────────────────────────────

format:  ## Format code with black + isort
	$(BLACK) peq_app/ tests/
	$(ISORT) peq_app/ tests/

format-check:  ## Check formatting without changing files (CI-ready)
	$(BLACK) --check --diff peq_app/ tests/
	$(ISORT) --check-only --diff peq_app/ tests/

lint:  ## Lint with pylint (errors + warnings only)
	$(PYLINT) --errors-only peq_app/

lint-full:  ## Lint with pylint (all checks)
	$(PYLINT) peq_app/

lint-all: format-check lint-full  ## Run all code quality checks

# ── Installation ─────────────────────────────────────────────────────────────

install-system:  ## Install Linux-PEQ to /usr/local/bin (requires sudo)
	@if [ ! -f /usr/local/bin/Linux-PEQ ]; then \
		echo "→ Installing Linux-PEQ to /usr/local/bin/"; \
		sudo ln -sf "$(CURDIR)/scripts/Linux-PEQ" /usr/local/bin/Linux-PEQ; \
		echo "✓ Installed — type 'Linux-PEQ' to launch."; \
	else \
		echo "Already installed: $$(readlink -f /usr/local/bin/Linux-PEQ)"; \
	fi

install-user:  ## Install Linux-PEQ to ~/.local/bin (no sudo needed)
	@mkdir -p "$${HOME}/.local/bin"
	@ln -sf "$(CURDIR)/scripts/Linux-PEQ" "$${HOME}/.local/bin/Linux-PEQ"
	@echo "✓ Installed to ~/.local/bin/Linux-PEQ"
	@echo "  Make sure ~/.local/bin is in your PATH."

uninstall:  ## Remove Linux-PEQ from /usr/local/bin
	@sudo rm -f /usr/local/bin/Linux-PEQ
	@rm -f "$${HOME}/.local/bin/Linux-PEQ"
	@echo "✓ Uninstalled Linux-PEQ"

# ── Cleanup ──────────────────────────────────────────────────────────────────

clean:  ## Remove venv, egg-info, and cache dirs
	rm -rf $(VENV)
	rm -rf peq_app.egg-info
	rm -rf __pycache__ peq_app/**/__pycache__ tests/__pycache__
