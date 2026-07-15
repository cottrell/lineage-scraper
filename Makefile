.PHONY: install dev tool clean crawl help lint test

help:
	cat Makefile

install:
	uv pip install -e .

dev:
	uv pip install -e ".[dev]"

tool:
	uv tool install -e .

lint:
	python -m ruff check lineage_scraper.py

test:
	python -m pytest -q --disable-warnings --maxfail=1 --ignore=old

clean:
	rm -rf build/ dist/ *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .cache .ruff_cache .mypy_cache .pytest_cache
