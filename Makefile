# The targets in this makefile should be executed inside Poetry, i.e. `poetry run make
# check`.

check: mypy test

coverage:
	poetry run codecov

mypy:
	mypy trio_jsonrpc/

test:
	pytest --cov=trio_jsonrpc/ tests/
	coverage report -m
