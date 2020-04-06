check: mypy test

mypy:
	mypy trio_jsonrpc/

test:
	pytest --cov=trio_jsonrpc/ tests/
	coverage report -m
