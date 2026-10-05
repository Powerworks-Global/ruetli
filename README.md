# Rütli

**Event-sourced, Eunomia-gated agent audit ledger for Apertus 1.5.** Submission for [Hack Apertus](https://hackapertus.ch/), Track 2B, Team Powerworks (William Power). Deadline: 2026-10-16.

Named for the 1291 oath that founded the Swiss Confederation — a mutual-trust, mutual-verification pact between parties who need to independently verify each other's commitments. An audit/policy-gated agent ledger is itself a mutual-verification system: the agent proves what it did, the ledger proves it can't lie about it afterward.

**The problem:** deploying an autonomous agent in a regulated setting (public administration, finance) needs non-repudiable proof of *why* it was allowed to take an action, not just a log that it happened. Rütli wraps an Apertus 1.5 agent runner with a policy gate ([Eunomia](https://github.com/whataboutyou-ai/eunomia)) and an append-only, hash-chained event ledger: every prompt, policy decision, tool call, and model output is a typed, replayable, tamper-evident event — measured against a prompt-only-policy baseline on a scripted task set of legitimate, unauthorized, and prompt-injection attempts.

All project code lives in [`track_2b/`](track_2b/) per the HackApertus template structure — that directory is the actual submission root.

## Quick links

| | |
|---|---|
| **Technical report** | [`track_2b/technical_report.md`](track_2b/technical_report.md) — architecture, evaluation results, limitations, related-work differentiation, reproducibility |
| **Architecture Decision Records** | [`track_2b/docs/adrs/`](track_2b/docs/adrs/) — see table below |
| **Eval harness source** | [`track_2b/src/eval/`](track_2b/src/eval/) |
| **Tests** | [`track_2b/tests/`](track_2b/tests/) — 40 passing, stdlib `unittest`, no `pytest` dependency |

## Solution architecture

| Component | Role | Built this hackathon? |
|---|---|---|
| Apertus 1.5 (8B GGUF, local) | Agent runner / inference | No — pre-existing model, not modified |
| [`eunomia`](https://github.com/whataboutyou-ai/eunomia) (Apache 2.0) | Standalone authorization server — `/check` policy gate, signed Agent Passport tokens, MCP middleware | No — pre-existing, third-party, open-source. Disclosed per HackApertus submission requirements |
| Event-Sourced Agent Ledger (CQRS) | Append-only, hash-chained log of every prompt, policy check, tool call, and model output | Yes |
| Crypto-shredding key vault | Per-subject encryption of personal-data fields; GDPR/FADP erasure = destroy the key, not the event | Yes |
| WORM mirror | Local append-only (`chattr +a`) sidecar copy of every event; catches a sophisticated tamper that rewrites the primary ledger *and* its own hash chain consistently | Yes |
| Self-review reflection pass | Periodic, human-in-the-loop-only mining of the ledger for leak patterns, false-block drift, and latency outliers — advisory only, never self-modifies policy | Yes |
| Replay CLI | Deterministic scrub forward/backward through a recorded agent session | Yes |
| Eval harness | Scripted task runner producing the metrics table below | Yes |

**Data flow:** prompt → agent runner appends `PromptReceived` → runner calls Eunomia `/check` for the proposed tool call → `ALLOW`/`DENY` (+ reason) → runner appends `PolicyEvaluated` → on `ALLOW`, tool executes, runner appends `ToolExecutionCompleted` → Apertus synthesizes the answer → runner appends `ModelOutput`. Every event carries a hash chained to its parent, used for tamper detection. Full data-flow diagram and target-architecture constraints (on-prem / air-gapped / sovereign Swiss cloud — one is mandatory): [`technical_report.md` §2](track_2b/technical_report.md#2-architecture).

**Naming note:** "Rütli" is this submission's name only — unrelated to "Eunomia" (the third-party OSS dependency above) and unrelated to "EUnomia"/"Nomothetes" (a different, unrelated Powerworks product in a different domain). Three distinct names, kept distinct deliberately.

## Architecture Decision Records

| ADR | Decision | Status |
|---|---|---|
| [001](track_2b/docs/adrs/ADR-001%20%E2%80%94%20Decoupled%20Policy%20Engine%20over%20Synchronous%20Proxy.md) | Decoupled out-of-band policy engine with cryptographic Agent Passports, not a synchronous inline proxy — avoids making the policy check a single point of failure on the model's token-streaming path | Accepted |
| [002](track_2b/docs/adrs/ADR-002%20%E2%80%94%20Agent%20Passport%20Schema%20%26%20Cantonal%20Jurisdiction%20Claims.md) | Agent Passport schema and cantonal/sovereign jurisdiction claims | Accepted |
| [003](track_2b/docs/adrs/ADR-003%20%E2%80%94%20Event-Sourced%20Agent%20Ledger%20%26%20CQRS%20Audit%20Model.md) | Event-sourced, hash-chained, CQRS-projected ledger over relational audit tables or distributed tracing | Accepted |
| [004](track_2b/docs/adrs/ADR-004%20%E2%80%94%20Deterministic%20Edge%20Tokenization%20with%20Local%20Reconstitution.md) | Deterministic edge tokenization with ephemeral local reconstitution (Sovereign-Agent-Mesh track; documented, not built — that track was dropped in favor of Project 1 only) | Accepted (design only) |
| [005](track_2b/docs/adrs/ADR-005%20%E2%80%94%20Crypto-Shredding%20for%20GDPR%20%26%20FADP%20Erasure%20Compatibility.md) | Crypto-shredding for GDPR/FADP-compliant erasure without breaking the hash chain | Accepted |
| [006](track_2b/docs/adrs/ADR-006%20%E2%80%94%20Hackproof%20WORM%20Backup%20for%20the%20Event%20Ledger.md) | Local append-only WORM mirror now; RustFS Object Lock anchor documented as the stronger sovereign-cloud mode, not built this submission | Accepted |
| [007](track_2b/docs/adrs/ADR-007%20%E2%80%94%20Human-in-the-Loop%20Reflective%20Self-Review%20Layer.md) | Periodic, advisory-only self-review layer mining the ledger for improvement signals, designed to be fully deletable with no changes to the core ledger/policy/runner modules | Accepted, implemented |

## Evaluation

Baseline (prompt-only policy) vs. Rütli (Eunomia-gated), over a scripted task set mixing legitimate, unauthorized, and prompt-injection attempts. Full methodology, honest caveats about what's dev-stub-backend vs. real, and the related-work differentiation against LiteLLM: [`technical_report.md` §5–7](track_2b/technical_report.md#5-evaluation).

```bash
cd track_2b
make eval       # prints the baseline-vs-ours metrics table
make reflect    # ADR-007 self-review pass over the last eval batch — advisory only
```

## Testing

```bash
cd track_2b
make test       # 40 tests, stdlib unittest, no pytest dependency
```

Covers the ledger's hash-chain tamper detection, the WORM mirror's defense against a *sophisticated* tamper (one that rewrites the chain and recomputes every downstream hash consistently), crypto-shredding erasure semantics, policy gate scope matching, and the reflection layer's leak/drift/latency-outlier detection.

## Code quality, vulnerability scanning, and SBOM

Honest status as of this submission, not aspirational:

- **Linting/formatting:** not yet wired into CI. The codebase follows a consistent style by hand (docstring-first, `from __future__ import annotations`, dataclasses for value types) but nothing enforces it automatically yet. **TODO** before submission if time allows: `ruff check` + `ruff format` as a pre-commit hook or CI step.
- **Dependency vulnerability scanning:** not yet run. The only third-party runtime dependency is `cryptography>=42.0` ([`requirements.txt`](track_2b/requirements.txt)) — deliberately minimal attack surface by design, but not yet verified with a scanner. **TODO:** `pip-audit` (or GitHub's own Dependabot alerts, since the repo is public) before submission.
- **SBOM:** not yet generated. **TODO:** `cyclonedx-bom` or `syft` can generate one in minutes given the small dependency surface — worth doing once `eunomia`/Apertus runtime dependencies are pinned (see the reproducibility TODOs in `technical_report.md` §8), since the SBOM should reflect the real submission's dependency set, not the dev-stub harness's.
- **What *is* enforced today:** the 40-test suite above, run on every `make test` invocation, and the ledger's own cryptographic self-checks (`verify_chain`, `verify_against_worm`) — which are closer to a runtime integrity guarantee than code-quality tooling, and arguably the more load-bearing of the two for this project's actual claim.

## License

Apache 2.0 for this submission's code (see [LICENSE](LICENSE)). All HackApertus projects are open-sourced per the event's [Terms & Conditions](https://hackapertus.ch/terms-and-conditions).
