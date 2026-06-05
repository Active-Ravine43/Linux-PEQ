VENV ?= .venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip

.PHONY: all venv install run test clean

all: venv install

venv:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip

install: venv
	$(PIP) install -e ".[dev]"

run:
	$(PYTHON) -m peq_app

test:
	$(PYTHON) -m pytest tests/ -v

clean:
	rm -rf $(VENV)
	rm -rf peq_app.egg-info
	rm -rf __pycache__ peq_app/**/__pycache__ tests/__pycache__
