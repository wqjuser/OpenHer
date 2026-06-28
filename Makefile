.PHONY: install test typecheck compile check desktop-build

install:
	python -m pip install -r requirements-dev.txt

test:
	python -m pytest tests/ -q

typecheck:
	python -m pyright

compile:
	python -m py_compile main.py wechat_adapter.py
	python -m compileall agent engine memory persona providers server skills tests main.py wechat_adapter.py

check: typecheck compile test
	git diff --check

desktop-build:
	cd desktop/OpenHer && swift build
