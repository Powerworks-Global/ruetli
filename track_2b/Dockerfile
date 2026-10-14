# Rütli: Event-Sourced Eunomia-Gated Agent Audit Ledger for Apertus 1.5
# HackApertus 2026 (Track 2B: Own Project) - Team Powerworks
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Install system dependencies if required for cryptography and filesystem attributes
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    e2fsprogs \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run the complete end-to-end evaluation & verification pipeline by default
CMD ["sh", "-c", "echo '=================================================================' && echo ' Rütli: Apertus 1.5 Governance & Audit Verification Pipeline' && echo '=================================================================' && echo '\n[1/3] Running Unit Test Suite (61 tests)...' && python3 -m unittest discover -s tests -v && echo '\n[2/3] Running Evaluation Benchmark (Baseline vs. Ours)...' && python3 -m eval.cli run-eval && echo '\n[3/3] Running Reflective Self-Review Meta-Audit (ADR-007)...' && python3 -m eval.cli reflect && echo '\n=================================================================' && echo ' Rütli: All Verification Gates Successfully Passed' && echo '================================================================='"]
