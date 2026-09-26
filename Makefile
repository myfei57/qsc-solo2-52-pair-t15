.PHONY: run check test

run:
	python -m mixplant --data-dir var/state --web-dir web

check:
	python -m mixplant --check --data-dir var/state --web-dir web

test:
	python -m pytest
