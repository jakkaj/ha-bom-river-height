.PHONY: install install-dev test clean

# Default target
all: install

# Install production dependencies
install:
	pip install -r requirements.txt

# Install development dependencies (includes testing tools)
install-dev: install
	pip install coverage>=7.0.0 pylint>=2.15.0

# Run the full test suite
test:
	python -m unittest discover -s tests

# Run a specific isolated test
test-isolated:
	python tests/test_isolated.py --help

# Run test coverage
coverage:
	coverage run -m unittest discover -s tests
	coverage report -m

# Run code quality check
lint:
	pylint river_height/ tests/

# Clean up Python bytecode files and caches
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.py[co]" -delete
	find . -type f -name "*.so" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "*.egg" -exec rm -rf {} +
	find . -type d -name ".coverage" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +

# Display help information
help:
	@echo "Available targets:"
	@echo "  make install      - Install production dependencies"
	@echo "  make install-dev  - Install development dependencies"
	@echo "  make test         - Run the test suite"
	@echo "  make test-isolated - Run isolated test tool (use --help for options)"
	@echo "  make coverage     - Run test coverage analysis"
	@echo "  make lint         - Run code quality checks"
	@echo "  make clean        - Clean up Python bytecode files and caches"