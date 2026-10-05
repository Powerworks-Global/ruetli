# ADR-007: Human-in-the-Loop Reflective Self-Review Layer

**Status:** Proposed
**Date:** 2026-10-05
**Deciders:** William Power
**Project:** Swiss AI Hackathon — Apertus 1.5 (Core for Project 1: Rütli / Apertus-Auditor)

---

## Context

Mentor feedback from Oliver Grognuz (Apertus track, 2026-10-05) confirmed the Project-1-only scope but flagged a gap: the ledger as built (ADR-003, ADR-005, ADR-006) is purely a *record* — it proves what happened, cryptographically, after the fact. It has no mechanism for the system to look back over a period of operation and ask "did I get on well here?", then turn that into concrete, human-facing suggestions for improving its own behavior.

Without this, the submission's story stops at "trustworthy audit trail." Adding it extends the story to "trustworthy audit trail that also makes the agent demonstrably better over time" — directly responsive to the feedback, and a stronger fit for the EU AI Act Article 14 (human oversight) narrative already used elsewhere in this project: oversight is more convincing when the system itself surfaces what needs attention, rather than requiring a human to go mining the raw ledger.

This also bears on the separate LiteLLM differentiation concern raised in the same call: LiteLLM's observability layer reports *usage* (cost, latency, call volume). Nothing in that ecosystem turns a cryptographically verified audit trail into a governance-improvement feedback loop. This ADR is written assuming that gap is real, pending the LiteLLM feature-check still outstanding — see Related Documents.

---

## Decision Drivers

- **Must stay human-in-the-loop.** The mentor's framing was explicit: "provide information back to a human." Any design that lets the system modify its own policy, prompts, or scopes autonomously contradicts both that instruction and the project's existing EU AI Act Article 14 human-oversight story — this is a credibility risk if judges spot the inconsistency.
- **Must not compromise the existing audit guarantees.** The reflective layer analyzes the ledger; it must not require new write paths into the hot path (`ToolProposed` → `PolicyEvaluated` → `ToolExecuted`) that could add latency to the `avg_gate_latency_ms` metric already reported in `technical_report.md`.
- **Its own output should be auditable, not a side-channel.** If the system claims "I reviewed my own performance," that claim should itself be a verifiable fact in the same ledger — not a markdown file that could silently diverge from what was actually reviewed and when.
- **Timeline.** 11 days to 2026-10-16. Must be buildable as an additional read-side pass over the existing `Ledger` and `metrics.py` module, not a new subsystem.
- **Must be deletable.** This is a new, unproven feature added under time pressure, mid-sprint, on a single mentor's suggestion — exactly the kind of feature that might not earn its place by demo day. Per William's standing engineering tenet (deletability alongside auditability as core design principles for all his software), it must be possible to rip this out entirely — the module, the CLI subcommand, the event type and its consumer — without touching the write path (`ToolProposed` → `PolicyEvaluated` → `ToolExecuted`) or invalidating any existing hash chain, WORM mirror, or test. If reflection is removed, every prior event remains valid; `ReflectionGeneratedEvent`s already written simply become inert history, not something requiring a migration.

---

## Considered Options

| Option | Mechanism | Human-in-the-loop? | Latency impact | Build cost |
| :--- | :--- | :--- | :--- | :--- |
| **A: Real-time per-task self-critique** | Model critiques its own decision immediately after every `ToolExecuted` event, inline in the same run. | Yes, but noisy — a suggestion per task is too granular to act on. | High — adds inference on the hot path, pollutes `avg_gate_latency_ms`. | Low, but actively damages an existing metric. |
| **B: Periodic batch reflection pass (Chosen)** | A separate, on-demand/scheduled job reads completed runs from the `Ledger` (via `events_for_run` / across runs) plus `metrics.py` output, mines them for patterns, and emits a structured improvement report — appended to the ledger as a new event type, then rendered to markdown for a human. | Yes — strictly advisory, a human decides what to act on. | None — runs out-of-band, after the fact, like `tamper_detection_rate()` already does. | Moderate — new module (`eval/reflection.py`) + one new event type + one new CLI subcommand. |
| **C: Autonomous self-tuning** | System detects a pattern (e.g. a tool scope that's never used) and silently adjusts the policy gate's authorized scopes. | No — explicitly rejected by the mentor's framing and by the project's own human-oversight story. | N/A | N/A — rejected outright. |

---

## Decision Outcome

**We choose Option B: a periodic, out-of-band reflective pass over the existing ledger, strictly advisory, with its own output appended back into the ledger as a first-class auditable event.**

### What it mines for, concretely

Built on the same data `metrics.py` already computes (`ConditionMetrics`, `replay_fidelity`, `tamper_detection_rate`) plus a new scan over raw events:

1. **Repeated identical denials** — the same `task_id`/resource pattern hitting `PolicyEvaluated(decision=DENY)` more than once in a run or across a batch. Surfaced as: *"agent repeatedly attempted `<resource>` without authorization — review whether this is a misconfigured scope or a genuine policy violation worth escalating."*
2. **False-block drift** — `false_block_rate_pct` trending upward across successive batches (requires the reflection job to persist/compare prior batch metrics, not just the current one). Surfaced as: *"the gate is becoming more restrictive on legitimate tasks — review policy `<id>` for over-tightening."*
3. **Retry loops** — a `ToolProposed` denied, then immediately re-proposed with identical or near-identical arguments, rather than the model adapting. Surfaced as: *"agent wasted N inference turns retrying a denied action instead of adapting — consider prompting it to check authorization before proposing."*
4. **Gate latency outliers** — individual `gate_latency_ms` values far above the batch average. Surfaced as a performance note, not a policy note.

Each finding cites the specific `event_id`s it's drawn from, so a human reviewing the report can jump straight to the raw ledger evidence rather than trusting the summary blind — consistent with the project's own non-repudiation ethos.

### New event type

Add `ReflectionGeneratedEvent` to the event type list in ADR-003 (`PromptReceived | PolicyEvaluated | ToolProposed | ToolExecuted | ModelOutput` → add `ReflectionGenerated`). Payload: `{batch_id, runs_reviewed: [run_id...], findings: [{category, evidence_event_ids, suggestion}], generated_at}`.

This event is appended to the ledger like any other — hash-chained, WORM-mirrored (ADR-006) — so the system's self-assessment becomes itself a non-repudiable fact: a judge or auditor can verify not just what the agent did, but that a specific self-review ran, when, and exactly what it found, without trusting an out-of-band report that could be edited after the fact.

### New read projection

`ImprovementSuggestionsView` — alongside the `AuditTimelineView` and `ComplianceViolationView` already specified in ADR-003. Renders the latest `ReflectionGeneratedEvent` findings as a human-readable markdown block, surfaced via a new CLI subcommand (e.g. `eval reflect --since <batch_id>`), separate from the existing `replay` CLI.

### What this explicitly does not do

It does not change policy, scopes, or prompts on its own. It does not run inline with task execution. It is not a second audit mechanism competing with ADR-003/006 — it is a read-only consumer of them. If a finding warrants action, a human makes a separate, ordinary change to the policy configuration; that change then produces its own ordinary ledger events the next time it's exercised.

### Removal path

Implemented as a single new module (`eval/reflection.py`) plus one new CLI subcommand plus one new event type with its own dedicated projection. Nothing in `ledger.py`, `policy.py`, `runner.py`, `metrics.py`, or `worm_mirror.py` needs to change to support it, and nothing in those modules depends on it existing. To remove the feature entirely: delete `eval/reflection.py`, drop the CLI subcommand, and stop emitting `ReflectionGeneratedEvent`. Past `ReflectionGeneratedEvent`s already on the ledger stay exactly where they are — they're ordinary hash-chained events like any other, so removing the feature that generated them doesn't require a migration or invalidate `verify_chain()` for any run. The feature can be cut the night before submission, if it doesn't pay off, at near-zero cost.

---

## What Would Change This Decision

If judging feedback or the entry-guide re-read (outstanding as of this ADR) reveals that reflection/self-improvement is expected to be demonstrated live and autonomously (i.e. actually closing the loop, not just reporting), Option C would need to be revisited — but only with an explicit, logged human-approval step inserted before any policy change takes effect, to preserve the human-in-the-loop constraint.

---

## Related Documents
- [[ADR-003 — Event-Sourced Agent Ledger & CQRS Audit Model]]
- [[ADR-006 — Hackproof WORM Backup for the Event Ledger]]
- [[Swiss AI Hackathon — Apertus]]
- `Active_Projects/Swiss AI Hackathon — Apertus/Meetings/2026-10-05 — Call with Oliver Grognuz (Apertus Mentor).md` (source of this ADR's requirement)
- LiteLLM differentiation check — still outstanding, see mentor-call meeting note follow-ups
