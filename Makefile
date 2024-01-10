check: check-pylint check-ruff

check-pylint:
	@poetry run pylint custom_components/* --fix

check-ruff:
	@poetry run ruff check custom_components/*

codefix:
	@poetry run ruff check --fix custom_components/*

test:
	@poetry run pytest


.PHONY: check codefix test check-ruff