.PHONY: help venv install build serve clean

PORT ?= 8888
PYTHON ?= python3
VENV_PYTHON := .venv/bin/python

help:
	@echo "KEX-bench Leaderboard"
	@echo ""
	@echo "Available commands:"
	@echo "  make venv       Create a local Python virtual environment"
	@echo "  make install    Prepare local build environment"
	@echo "  make build      Build the static site into dist/"
	@echo "  make serve      Build and serve locally at http://localhost:$(PORT)"
	@echo "  make clean      Remove generated files"

venv:
	$(PYTHON) -m venv .venv

install: venv
	$(VENV_PYTHON) -m pip install -r requirements.txt

build:
	@if [ -x "$(VENV_PYTHON)" ]; then \
		$(VENV_PYTHON) build.py; \
	else \
		$(PYTHON) build.py; \
	fi

serve: build
	@echo ""
	@echo "Serving KEX-bench leaderboard at http://localhost:$(PORT)"
	@echo "Press Ctrl+C to stop."
	@echo ""
	@if [ -x "$(VENV_PYTHON)" ]; then \
		cd dist && ../$(VENV_PYTHON) -m http.server $(PORT); \
	else \
		cd dist && $(PYTHON) -m http.server $(PORT); \
	fi

clean:
	rm -rf dist __pycache__ .pytest_cache .venv
