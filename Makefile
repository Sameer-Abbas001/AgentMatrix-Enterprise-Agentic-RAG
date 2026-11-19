.PHONY: install test lint eval run
install:
	pip install -e '.[dev]'

test:
	pytest

lint:
	ruff check .

eval:
	python scripts/evaluate.py

run:
	uvicorn agentmatrix.api:app --host 0.0.0.0 --port 8000
