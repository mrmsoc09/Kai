PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

.PHONY: install test migrate verify-tools workflow-templates health-check smoke-workflow run-workflow-local seed-mvp

install:
	$(PIP) install -r requirements.txt

test:
	$(PYTHON) -m pytest -q

migrate:
	alembic upgrade head

verify-tools:
	$(PYTHON) scripts/verify_tool_registry_install.py

workflow-templates:
	$(PYTHON) - <<'PY'
from apps.backend.src.core.bugbounty_workflow_engine import list_workflow_templates
import json
print(json.dumps(list_workflow_templates(), indent=2))
PY

health-check:
	bash scripts/health_check.sh

smoke-workflow:
	bash scripts/smoke_test_workflow.sh

run-workflow-local:
	$(PYTHON) scripts/run_workflow_local.py --template workflow_recon_surface_map --target example.com --safe-mode

seed-mvp:
	$(PYTHON) scripts/seed_mvp_demo.py --apply --trigger-run
