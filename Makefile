.PHONY: help lint fmt test
.DEFAULT_GOAL := help

help:
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

lint: ## Run code linters
	uv run mypy anydi tests
	uv run ruff check anydi tests
	uv run ruff format anydi tests --check

fmt: ## Run code formatters
	uv run ruff check anydi tests --fix
	uv run ruff format anydi tests

test:  ## Run unit tests
	uv run pytest -vv tests --ignore=tests/ext/test_pytest_plugin.py --cov=anydi -p no:anydi -p no:testanydi
	uv run pytest -vv tests/ext/test_pytest_plugin.py --cov=anydi --cov-append
