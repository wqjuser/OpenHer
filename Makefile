PYTHON ?= .venv/bin/python

.PHONY: install test typecheck compile check integration-smoke data-inventory data-backup data-verify data-restore data-reset backend-acceptance-smoke backend-runtime-smoke backend-websocket-smoke backend-chat-smoke desktop-acceptance-smoke desktop-build

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
	$(PYTHON) -m py_compile scripts/integration/backend_websocket_smoke.py
	$(PYTHON) -m py_compile scripts/integration/backend_chat_smoke.py
	$(PYTHON) -m py_compile scripts/integration/desktop_acceptance_smoke.py
	$(PYTHON) -m py_compile scripts/data_lifecycle.py

check: typecheck compile test
	git diff --check

integration-smoke:
	RUN_OPENHER_INTEGRATION=1 $(PYTHON) scripts/integration/provider_smoke.py

data-inventory:
	$(PYTHON) scripts/data_lifecycle.py inventory

data-backup:
	$(PYTHON) scripts/data_lifecycle.py backup

data-verify:
	@if [ -z "$(BACKUP)" ]; then echo "Usage: make data-verify BACKUP=/path/to/openher-data.zip"; exit 2; fi
	$(PYTHON) scripts/data_lifecycle.py verify "$(BACKUP)"

data-restore:
	@if [ -z "$(BACKUP)" ]; then echo "Usage: make data-restore BACKUP=/path/to/openher-data.zip ARGS=--overwrite"; exit 2; fi
	$(PYTHON) scripts/data_lifecycle.py restore "$(BACKUP)" $(ARGS)

data-reset:
	$(PYTHON) scripts/data_lifecycle.py reset

backend-acceptance-smoke:
	$(PYTHON) scripts/integration/backend_acceptance_smoke.py

backend-runtime-smoke:
	$(PYTHON) scripts/integration/backend_runtime_smoke.py

backend-websocket-smoke:
	$(PYTHON) scripts/integration/backend_websocket_smoke.py

backend-chat-smoke:
	$(PYTHON) scripts/integration/backend_chat_smoke.py

desktop-acceptance-smoke:
	$(PYTHON) scripts/integration/desktop_acceptance_smoke.py

desktop-build:
	cd desktop/OpenHer && swift build
