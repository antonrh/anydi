.PHONY: help lint fmt
.DEFAULT_GOAL := help

help:
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

lint: ## Run code linters
	poetry run mypy initdi/ tests/
	poetry run ruff initdi/ tests/
	poetry run ruff format initdi/ tests/ --check

fmt: ## Run code formatters
	poetry run ruff initdi/ tests/ --fix
	poetry run ruff format initdi/ tests/

test:  ## Run unit tests
	poetry run pytest -vv --cov=initdi/
