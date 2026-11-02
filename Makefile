PY = .venv/bin/python

test:
	$(PY) -m pytest -q

lint:
	.venv/bin/ruff check .
