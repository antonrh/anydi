.PHONY: help lint fmt
.DEFAULT_GOAL := help

help:
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

lint: ## Run code linters
	poetry run black pyxdi/ tests/ examples/ --check
	poetry run isort pyxdi/ tests/ examples/ --check
	poetry run flake8 pyxdi/ tests/ examples/
	poetry run mypy pyxdi/ tests/ examples/

fmt: ## Run code formatters
	poetry run black pyxdi/ tests/ examples/
	poetry run isort pyxdi/ tests/ examples/
