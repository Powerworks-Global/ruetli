.PHONY: run test eval reflect docker-build docker-run

DOCKER ?= $(shell command -v docker 2>/dev/null || command -v podman 2>/dev/null)
IMAGE_NAME ?= ruetli-track2b:latest

# Primary submission target (HackApertus Track 2B requirement):
# Builds the Docker container and runs end-to-end verification.
# Automatically falls back to direct execution if no container daemon is active.
run:
	@if [ -n "$(DOCKER)" ]; then \
		echo "Building Rütli container image ($(IMAGE_NAME))..."; \
		if $(DOCKER) build -t $(IMAGE_NAME) . ; then \
			echo "Executing Rütli container..."; \
			$(DOCKER) run --rm $(IMAGE_NAME); \
		else \
			echo "Container build failed or daemon unavailable. Falling back to local runner..."; \
			$(MAKE) test && $(MAKE) eval && $(MAKE) reflect; \
		fi \
	else \
		echo "No container runtime found, running locally..."; \
		$(MAKE) test && $(MAKE) eval && $(MAKE) reflect; \
	fi

# Dependency-free unit tests (stdlib unittest, 61 passing tests).
test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

# Runs the eval harness with the agent + policy gate and prints the Section 5 metrics table.
eval:
	PYTHONPATH=src python3 -m eval.cli run-eval

# ADR-007: advisory-only self-review pass over the last `make eval` batch.
reflect:
	PYTHONPATH=src python3 -m eval.cli reflect

# Compiles technical_report.md into Powerworks_Report.pdf (max 6 pages per HackApertus spec).
pdf:
	python3 scripts/generate_report_pdf.py
