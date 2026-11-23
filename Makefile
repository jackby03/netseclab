PY ?= python
export PYTHONPATH := src
EXAMPLES := $(wildcard lab/examples/*.yaml)

.PHONY: help test lint types cov check validate render box vmdk clean

help:
	@echo "make test      ejecuta la suite"
	@echo "make lint      ruff: estilo y errores"
	@echo "make types     mypy: tipos"
	@echo "make cov       pruebas con cobertura"
	@echo "make check     lint + tipos + pruebas + cobertura"
	@echo "make validate  valida todas las topologías de ejemplo"
	@echo "make render    genera los planes en build/render/"
	@echo "make box       construye la caja (necesita Linux con KVM)"

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check src tests
	$(PY) -m ruff format --check src tests

types:
	$(PY) -m mypy

cov:
	$(PY) -m pytest --cov

check: lint types test

validate:
	$(PY) -m lab.cli validate $(EXAMPLES)

render:
	@for f in $(EXAMPLES); do \
		n=$$(basename $$f .yaml); \
		$(PY) -m lab.cli render $$f --out build/render/$$n >/dev/null; \
		echo "  build/render/$$n"; \
	done

box:
	bash ./images/box/build.sh

vmdk:
	bash ./images/box/build.sh vmdk

clean:
	rm -rf build .pytest-tmp .pytest_cache .coverage htmlcov
