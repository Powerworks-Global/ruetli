# ADR-005: Crypto-Shredding for GDPR & FADP Erasure Compatibility

**Status:** Accepted  
**Date:** 2026-10-04  
**Deciders:** William Power  
**Project:** Swiss AI Hackathon — Apertus 1.5 (Core for Project 1: Rütli / Apertus-Auditor)  

---

## Context

[[ADR-003 — Event-Sourced Agent Ledger & CQRS Audit Model]] commits to an append-only, SHA-256 hash-chained event ledger specifically because immutability is what makes the audit trail non-repudiable: mutating any stored event breaks the hash chain for every event after it, so tampering is mathematically detectable.

That same immutability conflicts with **GDPR Article 17** and the **Swiss FADP**'s equivalent erasure right whenever a ledger event contains personal data about an identifiable natural person (a citizen name, an AHV/AVS number, an IBAN tied to an individual, or — more subtly — a cantonal company UID that resolves to a sole proprietor). A data subject's erasure request cannot be honored by deleting or editing the event, because that is precisely the operation the hash chain is designed to make either impossible or detectable.

This submission's own evaluation data is synthetic only (see `technical_report.md` Section 4), so no real data subject has standing to make an erasure request against it. This ADR exists anyway, because the ledger pattern itself — not just this hackathon instance of it — is the thing being pitched into the Powerworks Consulting Technical Audit practice (DORA/AI Act compliance-as-code), where real personal data will flow through it. Designing the event schema to be erasure-compatible now is materially cheaper than retrofitting it after real data is already in the ledger.

---

## Decision Drivers

- **GDPR Art. 17 / FADP erasure rights** are not negotiable away by an architecture choice — when they apply, they override pure immutability for the personal-data fields specifically, not for the ledger as a whole.
- **ADR-003's non-repudiation guarantee must survive erasure.** Honoring an erasure request for one data subject must not be able to invalidate the hash chain, or weaken the audit trail, for events belonging to any other subject or to no subject at all.
- **Most ledger content is not personal data.** Policy decisions, tool names, scope checks, and timing metadata describe the *agent's* behavior, not a data subject. Erasure should be scoped to the specific fields that are personal data, not to whole events.
- **Reuses existing vocabulary.** [[ADR-004 — Deterministic Edge Tokenization with Local Reconstitution]] already defines a typed-entity classification (`CHE_PERSON`, `CHE_AHV`, `CHE_IBAN`, `CHE_CANTONAL_ID`) for exactly this kind of field. A second, inconsistent PII-detection pass would be redundant and a source of drift.

---

## Considered Options

| Option | Mechanism | Preserves Hash Chain? | Satisfies Erasure? | Cost |
| :--- | :--- | :--- | :--- | :--- |
| **A: Mutable redaction** | Directly null/overwrite the personal field in the stored event on request. | No — breaks the chain for every subsequent event, silently, unless every downstream hash is also recomputed. | Yes, naively. | Low to implement, catastrophic to audit integrity. |
| **B: Full event deletion + chain re-linking** | Remove the event entirely; recompute and re-sign every subsequent event's `parent_hash`. | Technically yes, but only by rewriting history — which is itself indistinguishable from the tampering ADR-003 exists to detect. | Yes. | High — operationally expensive, and destroys EU AI Act Art. 12 record-keeping for the surrounding causal sequence. |
| **C: Crypto-shredding (Chosen)** | Encrypt personal-data fields per data subject with a unique Data Encryption Key (DEK) before the event is hashed. The ciphertext — not plaintext — is what the hash chain covers, so it never needs to change. Erasure = destroy the DEK, not the event. | Yes — unconditionally. The chain is computed over ciphertext that never changes. | Yes, in substance: once the DEK is destroyed, the ciphertext is permanent, undecryptable noise to everyone, including us. | Moderate — requires a small, separate, intentionally-mutable key vault alongside the immutable ledger. |

---

## Decision Outcome

**We choose Option C: Crypto-shredding.**

### Implementation Blueprint

1. **Field classification.** Any event payload field tagged as personal data (reusing ADR-004's typed-entity vocabulary) is encrypted before the event is constructed. Non-personal fields (tool name, resource pattern, policy decision, timestamps, scopes) remain plaintext and are hashed as-is.
2. **Per-subject Data Encryption Key (DEK).** Each `subject_id` gets one symmetric key (Fernet / AES, authenticated encryption), generated on first use and stored in a **key vault** — a small, separate, deliberately mutable SQLite table, *outside* the hash-chained ledger table.
3. **Ciphertext is what gets hashed.** The event's `payload_hash` (ADR-003) is computed over the final payload *after* personal fields have been replaced by their ciphertext. This is the core property: the hash chain is permanently correct regardless of what happens to the DEK later, because the DEK's existence was never an input to the hash.
4. **Erasure = key destruction, not event mutation.** A data subject's erasure request deletes their one row from the key vault. Every ciphertext blob referencing that `subject_id`, anywhere in the ledger, across any number of past runs, becomes permanently undecryptable in that instant. No ledger row is touched. `verify_chain()` (ADR-003) continues to pass unchanged.
5. **Replay and audit views degrade gracefully.** The Replayable Audit Dashboard (ADR-003 §2) can still replay the full causal structure and verify tamper-evidence for a session with a shredded subject — it renders a `[DATA_ERASED: subject <id>]` placeholder in place of the plaintext, rather than failing or silently fabricating a value.
6. **No second PII-detection pass.** Field classification reuses ADR-004's existing typed-entity vocabulary, so "what counts as personal data" is answered once, not twice, across the two ADRs.

### What this does NOT do
This does not make the ledger GDPR-compliant end to end (that also needs a lawful basis, a retention policy, and a DPIA for any real deployment — out of scope for this ADR). It solves specifically the architectural conflict between "immutable for audit" and "erasable on request," which is the part that has to be decided *before* writing the event schema, not after.

---

## What Would Change This Decision

If a regulator or DPA rules that permanently undecryptable ciphertext retained indefinitely still constitutes "personal data retained" under FADP/GDPR — i.e., that erasure requires the bytes to be gone, not merely inaccessible — then Option B (full event deletion with chain re-linking) would be required instead, at substantially higher operational cost, and the ledger schema would need the subject-indexed structure this ADR already establishes to even locate what to delete.

---

## Related Documents
- [[ADR-003 — Event-Sourced Agent Ledger & CQRS Audit Model]]
- [[ADR-004 — Deterministic Edge Tokenization with Local Reconstitution]]
- [[Swiss AI Hackathon — Apertus]]
