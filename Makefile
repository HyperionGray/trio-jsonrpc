check: mypy test

mypy:
	poetry run mypy trio_jsonrpc/

test:
	poetry run pytest --cov=trio_jsonrpc/ tests/
	poetry run coverage report -m
