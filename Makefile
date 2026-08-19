check: check-pylint check-ruff check-mypy

check-pylint:
	@uv run pylint custom_components/*

check-ruff:
	@uv run ruff check custom_components/*

check-mypy:
	@uv run mypy custom_components/solarfocus

codefix:
	@uv run ruff check --fix custom_components/*

test:
	@uv run pytest


.PHONY: check check-pylint check-ruff check-mypy codefix test
