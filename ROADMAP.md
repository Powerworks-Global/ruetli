# Roadmap

Time-ordered, Now/Next/Later — not a backlog. "Now" is scoped to the 2026-10-16 submission deadline; everything else is explicitly post-hackathon and conditional on the submission's outcome, not committed work.

## Now (by 2026-10-16)

- **Swap the dev-stub agent/gate for real Apertus 1.5 8B (Ollama) + a running `eunomia-server`. DONE, 2026-10-12.** Run against a real pulled model and a real `eunomia-server` container (CPU-only, ephemeral cloud VM — not the local dev sandbox). `RUTLI_REAL_BACKENDS=1 make eval` real submission numbers:

  | Metric | Baseline | Ours |
  |---|---|---|
  | Unauthorized calls blocked (%) | 78.6% | 78.6% |
  | False-block rate on legitimate calls (%) | 25.0% | 25.0% |
  | Replay fidelity (hash chain verifies) | N/A (no ledger) | 97.7% |
  | Tamper detection on mutated logs (%) | N/A (no ledger) | 100.0% |
  | Added latency per tool call | N/A | 4.814 ms |

  **Flagged for review before submission, not yet explained**: replay fidelity is 97.7%, not 100%. Baseline-vs-ours parity on blocked/false-block rates (both 78.6%/25.0%, identical to the decimal) is also worth a second look — confirm that's expected (e.g. both backends hitting the same gate logic on these particular tasks) rather than a sign the "ours" path isn't actually exercising something different. Neither investigated yet; do this before the numbers go in the submission.
- **Expand the task set 22 → 30-50.** Current set is hand-authored and doesn't yet produce false positives by construction (§6 Limitations) — real Apertus inference may propose messier resource strings that stress the gate differently.
- **Requirements traceability doc.** Open thread from a 2026-10-05 mentor conversation about requirement→design→test→verification linkage: for the hackathon submission, this will be a hand-authored table (HackApertus judging criterion / submission requirement → ADR → implementation module → test(s) → verification evidence) added to `track_2b/docs/`, not run through the Nomothetes engine — that tool's import pipeline expects a specific markdown spec format (PowerGym-style `requirements.md`/`research.md`) this Python eval harness doesn't produce, and retrofitting that mapping isn't worth the risk this close to the deadline. Nomothetes's new `implementationRef`/`verificationStatus` annotation fields (added the same day) are a plausible fit for a *future* pass at this, once there's time to do the format conversion properly.
- **Demo video** (≤2 min, per submission requirements).
- **Pin the submission commit SHA and dependency digests** (Eunomia Docker image, Apertus GGUF quantisation) — not `latest`, per the reproducibility requirement in §8.

## Next (post-submission, 30-60 days — conditional on how judging lands)

- **Lint/CI, `pip-audit`, SBOM generation** — all named as explicit gaps in the root README's Code Quality section. None block the submission itself; all are real gaps if this becomes more than a hackathon entry.
- **Wire the self-review layer's output into something a human actually checks regularly** — ADR-007 is implemented and tested, but `make reflect` today is a manual, on-demand command. A real deployment would want this on a schedule, with its findings surfaced somewhere a human will actually see them (not just stdout).
- **RustFS Object Lock WORM anchor** for the sovereign-Swiss-cloud target architecture (ADR-006, Option B) — documented, not built. Real infrastructure work (standing up RustFS), not harness code.
- **EU AI Act / Swiss FADP compliance dossier generator** — one-click from the ledger to a human-oversight verification document, per the original project brief's Project 1 scope.

## Later (speculative — only if there's a real reason to)

- **Revisit Sovereign-Agent-Mesh (Project 4)** as a second deployment mode on top of the same ledger, rather than a competing prototype — only if eval results or market signal actually support it. This was deliberately cut from scope on 2026-10-03/04 and confirmed correct by the mentor on 2026-10-05; don't revive it on a hunch.
- **Powerworks Consulting productization** — this architecture (event-sourced audit ledger + policy gate + crypto-shredding) maps cleanly onto Powerworks's own Technical Audit / DORA / AI Governance consulting practice. Worth a deliberate look post-hackathon, not something to start building mid-submission.

## What this roadmap deliberately leaves out

No committed dates beyond the hackathon deadline itself — "Next" and "Later" are directions, not a schedule, until there's a real decision to invest further (judging result, a client conversation, a deliberate go/no-go). Don't read this as a promise of continued development.
