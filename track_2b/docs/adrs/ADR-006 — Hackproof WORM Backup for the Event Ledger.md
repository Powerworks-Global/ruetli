# ADR-006: Hackproof WORM Backup for the Event Ledger

**Status:** Accepted  
**Date:** 2026-10-04  
**Deciders:** William Power  
**Project:** Swiss AI Hackathon — Apertus 1.5 (Core for Project 1: Rütli / Apertus-Auditor)  

---

## Context

[[ADR-003 — Event-Sourced Agent Ledger & CQRS Audit Model]] gives the ledger a SHA-256 hash chain, verified by `verify_chain()`. That protects against a *naive* tamper: edit a row's payload without recomputing its hash, and the mismatch is immediately detectable.

It does **not** protect against a *sophisticated* tamper: an attacker (or a compromised process) with write access to the single SQLite file can rewrite an event's payload **and** recompute every downstream hash to match, producing an internally consistent but false chain. Nothing in ADR-003 requires the hash chain to live anywhere an attacker with DB access can't also reach. A single mutable file, however well hash-chained, is not "hackproof" — it's tamper-*evident* against careless tampering, not tamper-*proof* against a determined one.

A genuine WORM (Write-Once-Read-Many) backup closes this: an independent copy of the ledger, written to storage that the ledger process itself cannot overwrite or delete, so that even a fully compromised ledger process can't make its own forged history look consistent against the backup.

---

## Decision Drivers

- **"Hackproof" has to mean something stronger than "hash-chained."** The chain alone only detects tampering that forgets to recompute downstream hashes. A WORM backup must detect tampering that *does* recompute them, because the forged version still can't match an independent, write-once copy.
- **Open-source requirement.** This submission is open-sourced under CC-BY-4.0/Apache 2.0 (per the Eunomia dependency and HackApertus T&Cs) — the WORM mechanism itself should not introduce a proprietary vendor dependency a judge or adopter can't inspect or self-host.
- **Target architecture constraint (ADR-001/004 context).** The primary demo path is on-premise/air-gapped (see `technical_report.md` Section 2). Any WORM mechanism requiring network egress is, by definition, not usable on that path — it can only be an optional stronger mode for the sovereign-Swiss-cloud architecture variant.
- **Build cost vs. hackathon timeline.** A from-scratch notarization/anchoring service is out of scope before 2026-10-16; the mechanism chosen must be buildable with existing OS primitives or an existing OSS tool, not a new service.

---

## Considered Options

| Option | Mechanism | Air-gapped compatible? | Open-source? | Strength |
| :--- | :--- | :--- | :--- | :--- |
| **A: OS-level append-only mirror (Chosen, primary)** | Every event is also written to a second file opened append-only, with the Linux `chattr +a` immutable-append attribute set (kernel-enforced; removing it requires root/`CAP_LINUX_IMMUTABLE`, a privilege the ledger process itself does not need and should not hold). | Yes — purely local, no network. | Yes — Linux kernel feature, no dependency. | Moderate: defeats a compromised ledger *process* (it can't even see the attribute without separate elevated access), but not a compromised root/host. |
| **B: RustFS Object Lock anchor (Chosen, documented future mode)** | Periodically write the hash-chain's rolling root hash (and full event batches) to a self-hosted RustFS bucket with S3 Object Lock retention. RustFS (Apache 2.0, Rust, S3-compatible — github.com/rustfs/rustfs, 34k+ stars, actively maintained) implements the same Object Lock semantics as MinIO but with ~2.3x the GET throughput on small-to-mid object sizes per its published benchmarks, and is self-hostable inside Switzerland (satisfies sovereignty, matches the existing "sovereign Swiss cloud" target architecture option). | No — requires network egress to the RustFS instance, even if self-hosted. | Yes — Apache 2.0. | High: object-lock retention is enforced by a separate, independently-administered system; compromising the ledger host alone cannot touch it. |
| **B′: MinIO Object Lock anchor (considered, superseded by B)** | Same idea as B, on MinIO (Apache 2.0, S3-compatible, the established precedent for this pattern). | No. | Yes. | High, functionally equivalent to B, but slower under RustFS's own benchmarks and the less immediate reason: RustFS flagged by William directly as the project to use here. |
| **C: Proprietary cloud Object Lock (e.g. a vendor-managed bucket)** | Same idea as B, on a commercial managed object store. | No. | No — ties the OSS submission to a proprietary service. | High, same as B, but rejected on the open-source driver alone. |

---

## Decision Outcome

**We choose both A and B, scoped to different target architectures — not as alternatives, but as a tiered defense matching the three target architectures this submission already supports (ADR-002's jurisdiction/classification model and the Section 2 target-architecture statement):**

1. **Option A (local append-only mirror) is implemented now**, as the WORM backup for the on-premise/air-gapped primary demo path. Every ledger event is mirrored to a sidecar JSONL file; the mirror file has `chattr +a` applied where the host supports it (standard Linux; falls back to a warning, not a silent no-op, on filesystems/hosts where the attribute isn't available — e.g. this sandboxed dev environment, which must not be mistaken for the real guarantee). `verify_chain()` gains a cross-check mode that also replays the mirror and confirms it matches the primary ledger byte-for-byte.
2. **Option B (RustFS Object Lock anchor) is documented as the stronger mode for the sovereign-Swiss-cloud target architecture**, not built for this submission: periodically push the rolling Merkle/chain root to a self-hosted, Object-Lock-enabled RustFS bucket. This is future work (see `technical_report.md` Section 9), not a hackathon-week deliverable — it requires standing up RustFS, which is infrastructure, not harness code.
3. **Option B′ (MinIO) is superseded by B** — same guarantee, slower, no longer the first choice once RustFS was identified as a faster drop-in with the same Object Lock semantics.
4. **Option C is rejected** on the open-source driver alone, independent of its technical merits.

### What "hackproof" honestly means here, as of this submission
With Option A alone, the claim is: *tamper-evident against a compromised ledger application, not against a compromised host with root.* That is a real, meaningful, and honestly-stated improvement over ADR-003's single-file hash chain — it is not the stronger "even root can't rewrite history unnoticed" claim that Option B would provide. The technical report must state this distinction explicitly (judging criterion: Technical rigour) rather than imply the full guarantee from day one.

---

## What Would Change This Decision

If the hackathon's judging criteria or a specific judge profile (e.g. Prof. Dr. Thomas Schulthess, CSCS — transparency/verification) explicitly reward a working sovereign-cloud WORM anchor over polish elsewhere, Option B would move from "documented future mode" to "build this instead of the replay TUI." Until then, time is better spent on the harness and replay CLI already in progress.

---

## Related Documents
- [[ADR-003 — Event-Sourced Agent Ledger & CQRS Audit Model]]
- [[ADR-005 — Crypto-Shredding for GDPR & FADP Erasure Compatibility]]
- [[Swiss AI Hackathon — Apertus]]
