.PHONY: install test typecheck compile check integration-smoke desktop-build

install:
	python -m pip install -r requirements-dev.txt

test:
	python -m pytest tests/ -q

typecheck:
	python -m pyright

compile:
	python -m py_compile main.py wechat_adapter.py
	python -m compileall agent engine memory persona providers server skills tests main.py wechat_adapter.py
	python -m py_compile scripts/integration/provider_smoke.py

check: typecheck compile test
	git diff --check

integration-smoke:
	RUN_OPENHER_INTEGRATION=1 python scripts/integration/provider_smoke.py

desktop-build:
	cd desktop/OpenHer && swift build
