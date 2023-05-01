.PHONY: help lint fmt
.DEFAULT_GOAL := help

help:
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

lint: ## Run code linters
	poetry run black pyxdi/ tests/ --check
	poetry run ruff check pyxdi/ tests/
	poetry run mypy pyxdi/ tests/

fmt: ## Run code formatters
	poetry run black pyxdi/ tests/
	poetry run ruff check pyxdi/ tests/ --fix


test:  ## Run unit tests
	poetry run pytest -vv --cov=pyxdi/
