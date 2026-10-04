.PHONY: run test eval

# Replace with the command that starts the project in a Docker container,
# e.g. `docker compose up`. It must work from a clean checkout.
# TODO: this is the real submission target — wire real Apertus 1.5 8B
# (Ollama) + a running eunomia-server container before 2026-10-16.
run:
	@echo "make run is not implemented yet — edit this Makefile"; exit 1

# Dependency-free unit tests (stdlib unittest, no pytest required).
test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

# Runs the eval harness with the dev-stub agent + ScopePolicyGate stand-in
# and prints the Section 5 metrics table. NOT the submission's `make run` —
# see the TODO above.
eval:
	PYTHONPATH=src python3 -m eval.cli run-eval
