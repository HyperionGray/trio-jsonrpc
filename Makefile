# The targets in this makefile should be executed inside Poetry, i.e. `poetry run make
# check`.

.PHONY: docs

check: mypy test

coverage:
	poetry run codecov

docs:
	$(MAKE) -C docs html

mypy:
	mypy trio_jsonrpc/

test:
	pytest --cov=trio_jsonrpc/ tests/
	coverage report -m
