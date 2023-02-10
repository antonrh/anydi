lint: ## Run code linters
	poetry run black pyxdi/ tests/ --check
	poetry run isort pyxdi/ tests/ --check
	poetry run flake8 pyxdi/ tests/
	poetry run mypy pyxdi/ tests/

fmt: ## Run code formatters
	poetry run black pyxdi/ tests/
	poetry run isort pyxdi/ tests/