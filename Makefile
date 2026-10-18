.PHONY: help setup check test validate models run clean

PYTHON ?= python
VENV_DIR ?= .venv

help:
	@echo "SeeGuide Automation Targets:"
	@echo "  setup     - Create virtual environment and install dependencies"
	@echo "  check     - Verify runtime environment (Python >=3.11, OpenCV 5.x, FastAPI)"
	@echo "  test      - Run test suite with pytest"
	@echo "  validate  - Run contract validation suite against schemas"
	@echo "  models    - Download and verify OpenCV Zoo ONNX model weights"
	@echo "  run       - Start FastAPI WebSocket server via uvicorn"
	@echo "  clean     - Remove temporary caches and artifacts"

setup:
	$(PYTHON) -m venv $(VENV_DIR)
	@echo "Virtual environment created at $(VENV_DIR)."
	@echo "Install dependencies with: $(VENV_DIR)/bin/pip install -r requirements.txt (Linux/macOS) or $(VENV_DIR)\Scripts\pip.exe install -r requirements.txt (Windows)"

check:
	$(PYTHON) scripts/check_environment.py

test:
	pytest tests/

validate:
	$(PYTHON) scripts/validate_contracts.py

models:
	$(PYTHON) scripts/download_models.py

run:
	uvicorn server.main:app --reload --host 0.0.0.0 --port 8000

clean:
	rm -rf __pycache__ */__pycache__ */*/__pycache__ .pytest_cache
