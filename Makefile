PYTHON ?= .venv/bin/python

.PHONY: install test typecheck compile check integration-smoke backend-acceptance-smoke backend-runtime-smoke desktop-build

install:
	$(PYTHON) -m pip install -r requirements-dev.txt

test:
	$(PYTHON) -m pytest tests/ -q

typecheck:
	$(PYTHON) -m pyright

compile:
	$(PYTHON) -m py_compile main.py wechat_adapter.py
	$(PYTHON) -m compileall agent engine memory persona providers server skills tests main.py wechat_adapter.py
	$(PYTHON) -m py_compile scripts/integration/provider_smoke.py
	$(PYTHON) -m py_compile scripts/integration/backend_acceptance_smoke.py
	$(PYTHON) -m py_compile scripts/integration/backend_runtime_smoke.py

check: typecheck compile test
	git diff --check

integration-smoke:
	RUN_OPENHER_INTEGRATION=1 $(PYTHON) scripts/integration/provider_smoke.py

backend-acceptance-smoke:
	$(PYTHON) scripts/integration/backend_acceptance_smoke.py

backend-runtime-smoke:
	$(PYTHON) scripts/integration/backend_runtime_smoke.py

desktop-build:
	cd desktop/OpenHer && swift build
