.PHONY: help lint fmt test
.DEFAULT_GOAL := help

help:
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

lint: ## Run code linters
	poetry run mypy anydi tests
	poetry run ruff check anydi tests
	poetry run ruff format anydi tests --check

fmt: ## Run code formatters
	poetry run ruff check anydi tests --fix
	poetry run ruff format anydi tests

test:  ## Run unit tests
	poetry run pytest -vv tests --ignore=tests/ext/test_pytest_plugin.py --cov=anydi -p no:anydi -p no:testanydi
	poetry run pytest -vv tests/ext/test_pytest_plugin.py --cov=anydi --cov-append
