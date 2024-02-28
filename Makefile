.PHONY: help lint fmt
.DEFAULT_GOAL := help

help:
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

lint: ## Run code linters
	poetry run mypy anydi tests
	poetry run ruff anydi tests
	poetry run ruff format anydi tests --check

fmt: ## Run code formatters
	poetry run ruff anydi tests --fix
	poetry run ruff format anydi tests

test:  ## Run unit tests
	poetry run pytest -vv --cov=anydi/
