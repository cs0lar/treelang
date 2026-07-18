PYTHON_PATHS = treelang tests evaluation cookbook/*.py

.PHONY: install format lint typecheck test build check clean

install:
	uv sync --frozen --all-groups

format:
	uv run ruff check --fix $(PYTHON_PATHS)
	uv run ruff format $(PYTHON_PATHS)

lint:
	uv run ruff check $(PYTHON_PATHS)
	uv run ruff format --check $(PYTHON_PATHS)

typecheck:
	uv run mypy

test:
	uv run pytest

build:
	uv build

check: lint typecheck test build

clean:
	rm -rf build dist .coverage coverage.xml .mypy_cache .pytest_cache .ruff_cache
