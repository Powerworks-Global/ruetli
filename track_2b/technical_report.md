# Technical report — `Rütli`

A deeper write-up than the README: what you built, how it works, and what the
numbers say.

- **Track:** Track 2B — Rütli (Apertus-Auditor)
- **Event:** Online
- **Team:** Powerworks — William Power
- **Demo:** `link to video` _(TODO: record ≤2 min demo before submission)_

## 1. Summary

`TODO — one paragraph once Section 5 has real numbers.` Draft: Agentic AI deployments in regulated sectors (public administration, finance) need non-repudiable proof of *why* an agent was allowed to take an action, not just a log that it happened. Rütli — named for the 1291 oath that founded the Swiss Confederation, a mutual-trust pact between parties who need to verify each other's commitments — wraps an Apertus 1.5 agent runner with a policy gate and an append-only, hash-chained event ledger: every prompt, policy check, tool call, and model output is recorded as a typed, replayable event. We measure this against a prompt-only-policy baseline on a scripted task set mixing legitimate calls, unauthorized calls, and prompt-injection attempts, and report blocked-unauthorized-call rate, false-block rate, replay fidelity, and tamper detection.

## 2. Architecture

**Components:**

| Component | Role | Pre-existing or built this hackathon |
|---|---|---|
| Apertus 1.5 (8B GGUF, local) | Agent runner / inference | Pre-existing (Apertus model, not modified) |
| [`eunomia`](https://github.com/whataboutyou-ai/eunomia) (Apache 2.0) | Standalone authorization server — `/check` policy gate, signed Agent Passport tokens, MCP middleware | **Pre-existing, third-party, open-source.** We did not build this. Disclosed per HackApertus submission requirements. |
| Event-Sourced Agent Ledger (CQRS) | Append-only, hash-chained log of every prompt, policy check, tool call, and model output | Built this hackathon |
| Replay CLI/TUI | Deterministic scrub forward/backward through a recorded agent session | Built this hackathon |
| Eval harness | Scripted task runner producing the Section 5 metrics | Built this hackathon |

**Data flow:** User prompt → Apertus agent runner appends `PromptReceivedEvent` → runner calls Eunomia `/check` for the proposed tool call → Eunomia returns `ALLOW`/`DENY` (+ reason) → runner appends `PolicyEvaluatedEvent` → on `ALLOW`, runner executes the tool, appends `ToolExecutionCompletedEvent` → Apertus synthesizes the final answer → runner appends `ModelOutputEvent`. Every event carries a `PayloadHash` and `ParentEventId`, forming a hash chain used for tamper detection (Section 5).

Diagrams: see `[[ADR-003 — Event-Sourced Agent Ledger & CQRS Audit Model]]` sequence diagram in the parent vault note — `TODO: copy into docs/architecture.png` before submission.

**Naming note:** "Rütli" is this submission's name only. It is unrelated to "Eunomia" (the third-party OSS dependency above) and unrelated to "EUnomia"/"Nomothetes" (an unrelated Powerworks product, a different domain entirely, being renamed separately). Three distinct things, kept distinct deliberately after an internal naming collision was caught during setup.

### Target architecture (mandatory)

Rütli is deployable as:

- **a) On-premise** — Eunomia server, the Apertus 8B GGUF runner, and the event ledger (SQLite/Postgres) all run in one Docker Compose stack on infrastructure we administer. This is the primary demo path.
- **b) Air-gapped** — satisfied provided all dependencies (model weights, `eunomia-ai` package, Docker base images) are pulled at **build time** and nothing egresses at **runtime**. This split is enforced in the `Dockerfile`/`Makefile`: `TODO — confirm no runtime network calls remain once the 70B CSCS path is excluded from this track's demo.`
- c) Sovereign Swiss cloud — not used for this track (would require the CSCS 70B API path; out of scope once we down-selected to the on-prem/air-gapped Auditor story over the Sovereign-Agent-Mesh track).

**External dependencies** (build-time only, per the air-gapped constraint above):
- `swiss-ai/Apertus-v1.5-8B` weights (GGUF quantization, via Ollama/llama.cpp)
- `eunomia-ai` Python package or `ttommitt/eunomia-server` Docker image — **pin to a digest, not `latest`**, before submission (reproducibility requirement, Section 7)
- Standard Python/Docker base images

## 3. Use of Apertus

- **Model:** `swiss-ai/Apertus-v1.5-8B` (local GGUF, via Ollama/llama.cpp)
- **How it is used:** agents / tool use — Apertus proposes tool calls, which are gated by Eunomia before execution
- **Where it runs:** locally, on the demo machine, no external API calls at runtime (air-gapped target architecture)

Every tool-call failure, malformed JSON response, and policy refusal from Apertus is logged from day one — this feeds both Section 5 (false-block rate needs to know when the *model*, not the gate, caused a refusal) and Section 6 (limitations).

`TODO: prompt template, quantisation level, and llama.cpp/Ollama version pin once the runner is built.`

## 4. Data

**Synthetic only** — no human-subject or personal data, which sidesteps consent/licensing questions entirely (per mentor guidance).

- **Task set:** 30–50 scripted agent tasks, authored by us, mixing:
  - Legitimate tool calls (should be allowed)
  - Unauthorized tool calls (should be blocked)
  - Prompt-injection attempts (should be blocked, and should be distinguishable from a legitimate refusal in the ledger)
- **Size:** well under the 100 MB `data/` limit.
- **Licence:** our own authorship — CC-BY-4.0, same as the rest of the submission.

`TODO: link the finished task set file in data/ once authored.`

## 5. Evaluation

**Baseline:** the same Apertus agent with the authorization policy stated only in the system prompt — no Eunomia gate, no ledger.
**Ours:** the same agent with the Eunomia `/check` gate in front of every tool call, plus the event ledger recording each decision.

| Metric | Why it matters | Baseline | Ours |
|---|---|---|---|
| Unauthorized calls blocked (%) | Headline result — does the gate actually stop what the prompt-only policy misses? | TBD | TBD |
| False-block rate on legitimate calls (%) | Stops "block everything" from trivially winning | TBD | TBD |
| Replay fidelity (ledger replays to identical final state; hash chain verifies) | Proves the audit/non-repudiation claim, not just that logging happened | N/A (no ledger) | TBD |
| Tamper detection on mutated logs (%) | Proves tamper-evidence, not just tamper-logging | N/A (no ledger) | TBD |
| Added latency per tool call (ms) | The operational cost of the gate — judged under "Value, cost & scalability" | N/A | TBD |

Expectation (per mentor feedback, to confirm or refute with data): the prompt-only baseline leaks on prompt-injection cases specifically — this is the result that makes the audit-layer's case with numbers instead of assertion.

## 6. Limitations

`TODO — fill once the eval harness runs.` Known candidates to check: Eunomia `/check` adds latency per tool call (measure, don't assume); the 8B model's own instruction-following failures vs. gate failures need to stay distinguishable in the ledger; air-gapped claim (Section 2) needs re-verification after every dependency version bump, not just once at the start.

## 7. Reproducibility

- **Hardware:** `TODO — spec the demo machine`
- **Runtime:** Docker Compose, `make run` from repo root
- **Seeds:** task-set generation and any sampling in the eval harness must be seeded and the seed recorded here
- **Commit:** `TODO — pin the exact submission commit SHA here on the day of submission`
- **Dependency pins:** Eunomia Docker image digest (not `latest`), vLLM/llama.cpp version, Apertus GGUF quantisation — all pinned, per the mentor's "write the `make run` target and pin the commit on day 1, not in the last hour" guidance.

## 8. Next steps

What we would build with another month: the EU AI Act / Swiss FADP automated compliance dossier generator (one-click from the ledger to a human-oversight verification document), and — if the eval results support it — revisit the Sovereign-Agent-Mesh track (dual-model edge/cloud routing) as a second deployment mode on top of the same ledger, rather than a competing prototype.

## License

Creative Commons Attribution 4.0 (CC-BY-4.0). All HackApertus projects are open-sourced.

## References

- Apertus 1.5: https://huggingface.co/swiss-ai/Apertus-v1.5-8B
- Eunomia (OSS authorization layer, Apache 2.0): https://github.com/whataboutyou-ai/eunomia
- HackApertus Track 2B template: https://github.com/HackApertus/project-template/tree/main/track_2b
- `TODO: ADR links once copied/published alongside the repo.`
