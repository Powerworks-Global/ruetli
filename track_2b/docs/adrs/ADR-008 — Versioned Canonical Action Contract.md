# ADR-008: Versioned Canonical Action Contract

**Status:** Accepted — implemented in evaluation harness; live backend verification pending
**Date:** 2026-10-08
**Deciders:** William Power
**Project:** Rütli — Apertus agent auditor

## Context

The evaluation runner checks a model-proposed resource but records the fixture's expected tool and resource as executed. A permitted but incorrect proposal can therefore produce misleading audit evidence. Authorization also ignores the proposed tool, and an absent/malformed tool call can be counted as a model refusal. The current harness simulates execution; it does not operate an external tool.

## Decision

Introduce a versioned, validated action contract between the model and policy gate. A registry defines permitted tools, operations and resource namespaces. Runtime validation is authoritative even when a model API advertises a JSON schema. Keep fixture expectations separate from proposals. Pass the *same validated action* to authorization, simulated execution and the ledger. Authorize tool and operation as well as resource. Preserve trusted identity and entitlements outside model output.

Record proposal, validation, policy decision and simulated execution as separate evidence. Do not duplicate personal resource identifiers in plaintext alongside encrypted fields. Report malformed output, model refusal, policy error and denial separately, and distinguish correct action selection from merely receiving authorization. Historical ledger events remain readable; new payloads carry a contract version.

The evaluation baseline and gated condition share validation; only the policy gate differs. This contract is an extension point for a real executor, not proof that an external action occurred or that model output is deterministic.

## Alternatives

Prompt-only normalization leaves ambiguous and unvalidated proposals. A full UI ontology adds DOM/VLM grounding and script compilation that this project does not currently use. If UI automation is added later, grounding adapters can target this contract.

## Verification

- Invalid or unknown actions never reach the executor.
- The action authorized is the one recorded as simulated execution.
- A permitted resource does not authorize a different tool or operation.
- Wrong-but-permitted actions count as selection errors.
- Failures and refusals remain separate from policy denials.
- Sensitive identifiers are stored only in protected payloads where subject keys are used.
- Old ledger runs still verify without migration.

## Related decisions

[ADR-001](ADR-001%20%E2%80%94%20Decoupled%20Policy%20Engine%20over%20Synchronous%20Proxy.md) (policy engine), [ADR-003](ADR-003%20%E2%80%94%20Event-Sourced%20Agent%20Ledger%20%26%20CQRS%20Audit%20Model.md) (ledger), [ADR-005](ADR-005%20%E2%80%94%20Crypto-Shredding%20for%20GDPR%20%26%20FADP%20Erasure%20Compatibility.md) (erasure), [ADR-007](ADR-007%20%E2%80%94%20Human-in-the-Loop%20Reflective%20Self-Review%20Layer.md) (reflection).
