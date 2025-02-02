check: check-pylint check-ruff

check-pylint:
	@uv run pylint custom_components/*

check-ruff:
	@uv run ruff check custom_components/*

codefix:
	@uv run ruff check --fix custom_components/*

test:
	@uv run pytest


.PHONY: check codefix test check-ruff