PY ?= python
export PYTHONPATH := src
EXAMPLES := $(wildcard lab/examples/*.yaml)

.PHONY: help test render validate box clean

help:
	@echo "make test      ejecuta la suite"
	@echo "make validate  valida todas las topologías de ejemplo"
	@echo "make render    genera los planes en build/render/"

test:
	$(PY) -m pytest

validate:
	$(PY) -m lab.cli validate $(EXAMPLES)

render:
	@for f in $(EXAMPLES); do \
		n=$$(basename $$f .yaml); \
		$(PY) -m lab.cli render $$f --out build/render/$$n >/dev/null; \
		echo "  build/render/$$n"; \
	done

box:
	./images/box/build.sh

vmdk:
	./images/box/build.sh vmdk

clean:
	rm -rf build .pytest-tmp .pytest_cache
