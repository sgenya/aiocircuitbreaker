TESTS_REPORT := $(CURDIR)/$(TMP)/tests
HTMLCOV := $(TESTS_REPORT)/htmlcov

clean:
	find . -type d -name '.mypy_cache' -exec rm -rf {} +
	find . -type d -name '__pycache__' -exec rm -rf {} +
	find . -type d -name '*pytest_cache*' -exec rm -rf {} +
	find . -type f -name "*.py[co]" -exec rm -rf {} +


build-dev-image:
	docker build -t aiocircuitbreaker-dev -f ./Dockerfile ./ --no-cache

# ================================================================================
# R E Q U I R E M E N T S
# ================================================================================
install-pre-commit:
	@pre-commit install && pre-commit install --hook-type commit-msg

requirements:
	pip install --upgrade pip
	poetry install --remove-untracked
	make install-pre-commit

requirements-update:
	poetry update

# ================================================================================
# FORMAT
# ================================================================================
format: install-pre-commit
	pre-commit run --all-files --hook-stage manual


# ================================================================================
# TESTS
# ================================================================================
test:
	pytest .

coverage-combine:
	coverage combine $(TESTS_REPORT)/*.cov

coverage-report: coverage-combine
	coverage report

coverage-html-report: coverage-combine
	coverage html -d $(HTMLCOV)


# ================================================================================
# PYPI
# ================================================================================
build-package:
	poetry build
