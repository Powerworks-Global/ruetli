# Requirements & Judging Criteria Traceability Matrix

This matrix formalizes the end-to-end linkage between **HackApertus Track 2B judging criteria & regulatory requirements**, architectural invariants (**ADRs**), concrete **implementation modules**, machine-checkable **unit test suites**, and verifiable **operational evidence**.

---

## 1. HackApertus Judging Criteria Traceability

| Judging Criterion (Scale 0–5) | Focus & Requirement | Architecture Decision | Implementation Module | Automated Test Gate | Operational Verification Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Purposeful use of AI** | Agent tool use with Apertus 1.5 in regulated European contexts; governed action synthesis over unconstrained prompting. | [ADR-001](../docs/adrs/ADR-001%20%E2%80%94%20Decoupled%20Policy%20Engine%20over%20Synchronous%20Proxy.md)<br>[ADR-008](../docs/adrs/ADR-008%20%E2%80%94%20Versioned%20Canonical%20Action%20Contract.md) | `src/eval/agent.py`<br>`src/eval/actions.py` | `tests/test_agent.py`<br>`tests/test_action_contract.py` | Apertus proposed actions conform to finite canonical action contract; ambiguous/unauthorized tool calls separated from valid proposals. |
| **2. Technical Rigour** | Cryptographic non-repudiation, tamper-evidence under sophisticated attack, and strict separation between proposal, authorization, and execution. | [ADR-003](../docs/adrs/ADR-003%20%E2%80%94%20Event-Sourced%20Agent%20Ledger%20%26%20CQRS%20Audit%20Model.md)<br>[ADR-006](../docs/adrs/ADR-006%20%E2%80%94%20Hackproof%20WORM%20Backup%20for%20the%20Event%20Ledger.md)<br>[ADR-008](../docs/adrs/ADR-008%20%E2%80%94%20Versioned%20Canonical%20Action%20Contract.md) | `src/eval/ledger.py`<br>`src/eval/worm.py`<br>`src/eval/actions.py` | `tests/test_ledger.py`<br>`tests/test_worm_mirror.py`<br>`tests/test_action_contract.py` | 100% detection of naive tampering (`verify_chain`); 100% detection of sophisticated hash-recalculation tampering via append-only WORM cross-check (`verify_against_worm`). |
| **3. Value, Cost & Scalability** | Low overhead policy evaluation; out-of-band asynchronous verification preventing token streaming bottlenecks; self-review optimization. | [ADR-001](../docs/adrs/ADR-001%20%E2%80%94%20Decoupled%20Policy%20Engine%20over%20Synchronous%20Proxy.md)<br>[ADR-007](../docs/adrs/ADR-007%20%E2%80%94%20Human-in-the-Loop%20Reflective%20Self-Review%20Layer.md) | `src/eval/policy.py`<br>`src/eval/reflection.py`<br>`src/eval/runner.py` | `tests/test_policy.py`<br>`tests/test_reflection.py` | Stand-in policy gate overhead < 0.03 ms; periodic advisory reflection detects false-block drift and repeated tool leak patterns without operator toil. |
| **4. Sovereign Deployability** | Strict on-premise / air-gapped capability; zero runtime internet egress; Swiss jurisdiction and cantonal claims handling; GDPR/FADP crypto-shredding. | [ADR-002](../docs/adrs/ADR-002%20%E2%80%94%20Agent%20Passport%20Schema%20%26%20Cantonal%20Jurisdiction%20Claims.md)<br>[ADR-005](../docs/adrs/ADR-005%20%E2%80%94%20Crypto-Shredding%20for%20GDPR%20%26%20FADP%20Erasure%20Compatibility.md) | `src/eval/crypto_shredding.py`<br>`src/eval/policy.py` | `tests/test_crypto_shredding.py`<br>`tests/test_policy.py` | Runs completely offline with local model weights (GGUF) and local Eunomia instance. Destruction of per-subject encryption keys completes regulatory erasure without breaking ledger hash chain. |
| **5. Implementation Feasibility** | Clean reproducible execution; dependency-free testing (stdlib `unittest`); containerized single-command launch (`make run`). | [ADR-003](../docs/adrs/ADR-003%20%E2%80%94%20Event-Sourced%20Agent%20Ledger%20%26%20CQRS%20Audit%20Model.md)<br>[ADR-007](../docs/adrs/ADR-007%20%E2%80%94%20Human-in-the-Loop%20Reflective%20Self-Review%20Layer.md) | `src/eval/cli.py`<br>`Makefile`<br>`Dockerfile` | `tests/` (all 61 passing tests) | Single containerized build (`docker build` / `make run`); test suite runs in < 0.3s on modest commodity x86 hardware. |

---

## 2. Regulatory & Compliance-as-Code Traceability

| Regulation & Article | Legal Requirement | Architectural & Technical Implementation | Verification Method |
| :--- | :--- | :--- | :--- |
| **EU AI Act — Article 12 (Record-keeping)** | Mandatory automated recording of events ("logs") throughout the system lifecycle, guaranteeing trace of operations and high-risk decision lineage. | Append-only event-sourced ledger (`src/eval/ledger.py`) recording `PromptReceived`, `PolicyEvaluated`, `ToolProposed`, `ToolExecutionCompleted`, and `ModelOutput` with SHA-256 parent chaining. | `tests/test_ledger.py`<br>`tests/test_worm_mirror.py` |
| **EU AI Act — Article 14 (Human Oversight)** | High-risk AI systems must be designed to enable natural persons to oversee operation, detect anomalies, and intervene. | Reflective self-review layer (`src/eval/reflection.py`) mining execution logs for drift, outliers, and systematic leaks, emitting structured audit findings (`make reflect`). | `tests/test_reflection.py` |
| **GDPR Art. 17 / Swiss FADP Art. 32 (Right to Erasure)** | Obligation to erase personal data upon subject request without invalidating legal accountability or records required by law. | Crypto-shredding key vault (`src/eval/crypto_shredding.py`) with per-subject AES-256 keys. Shredding deletes key material rendering stored ciphertext permanently unrecoverable while preserving hash-chain mathematical integrity. | `tests/test_crypto_shredding.py` |
| **Swiss FINMA / DORA Operational Resilience** | Protection of audit trails against administrative tampering, insider threat, and silent log alteration. | WORM sidecar mirror (`src/eval/worm.py`) enforcing append-only attributes (`chattr +a`), detecting attackers who recalculate ledger hashes post-compromise. | `tests/test_worm_mirror.py` |

---

## 3. Submission Deliverables Checklist

- [x] **Git Repository URL**: Public repository at `https://github.com/Powerworks-Global/ruetli`
- [x] **Technical Report PDF**: `track_2b/Powerworks_Report.pdf` (max 6 pages, complete architecture & benchmarks)
- [x] **Demonstration Video**: `track_2b/docs/demo/ruetli-demo.mp4` (1:52, offline narration via Piper TTS, unedited terminal capture)
- [x] **Containerized Execution (`make run`)**: Self-contained `Dockerfile` and automated `make run` target executing clean test suite, evaluation benchmarks, and self-review reflection
- [x] **Deterministic Test Coverage**: 61/61 automated tests passing via standard library `unittest`
