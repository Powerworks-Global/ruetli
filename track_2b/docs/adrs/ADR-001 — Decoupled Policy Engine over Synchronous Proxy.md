# ADR-001: Decoupled Out-of-Band Policy Engine with Cryptographic Passports over Synchronous Proxy

**Status:** Accepted  
**Date:** 2026-10-03  
**Deciders:** William Power  
**Project:** Swiss AI Hackathon — Apertus 1.5 (Shared Core for Auditor & Sovereign Mesh)  

---

## Context

Autonomous agents powered by **Apertus 1.5** execute external actions via the **Model Context Protocol (MCP)**. To guarantee compliance with European and Swiss regulatory standards (EU AI Act Art. 14, Swiss FADP), every tool invocation must be governed by an authorization layer (**Eunomia**).

Two architectural topologies were evaluated for integrating Eunomia:

1. **Synchronous Transparent Proxy / API Gateway**: All network calls, token streaming, and MCP tool traffic pass through a centralized Eunomia proxy container that inspects payloads on the wire.
2. **Decoupled Out-of-Band Policy Engine with Cryptographic Passports**: Eunomia acts as an out-of-band Policy Decision Point (PDP). It issues short-lived, cryptographically signed **Agent Passports**. The local agent runner hosts a lightweight Policy Enforcement Point (PEP) via an MCP interceptor that checks cached claims locally or queries Eunomia's `/check` endpoint asynchronously.

---

## Decision Drivers

- **Inference Latency & Streaming Jitter**: Apertus 1.5 runs across high-throughput endpoints (local 8B GGUF via Ollama and CSCS Alps supercomputer 70B with 262k context). Forcing token-generation streams through an inline proxy introduces latency, connection multiplexing overhead, and potential stream stalls.
- **Single Point of Failure (SPOF)**: A synchronous proxy failure crashes active agent execution, even for non-sensitive local tool executions.
- **Zero-Trust Cryptographic Non-Repudiation**: For the Auditor branch (Project 1), proof of authorization must be bound cryptographically to the agent session and verifiable offline by independent third-party auditors.
- **Local vs. Cloud Edge Compatibility**: In the Sovereign Mesh branch (Project 4), edge devices must be capable of offline or disconnected operation using cached cantonal policy boundaries.

---

## Considered Options

| Evaluation Metric | Synchronous Transparent Proxy | Decoupled Policy Engine + Cryptographic Passports (Chosen) |
| :--- | :--- | :--- |
| **Critical Path Latency** | High: Every token and tool round-trip incurs proxy network overhead. | Low: Model token streaming is direct; only discrete tool calls touch the PEP interceptor. |
| **Offline / Edge Resilience** | Zero: Disconnected edge cannot run if proxy connection drops. | High: Local PEP validates signed passport claims even under partial network partition. |
| **Audit Verification** | Ephemeral: Proxy logs require centralized capture. | Cryptographic: Passports are signed tokens embedded directly into the immutable event stream. |
| **Implementation Complexity** | Medium: Standard HTTP/reverse-proxy plumbing. | Medium-High: Requires passport token schema and PEP middleware interceptor in MCP runner. |
| **Failure Mode** | Fail-Closed halts the entire agent session. | Fail-Closed stops only unauthorized tool actions; agent reasoning remains intact. |

---

## Decision Outcome

**We choose Option 2: Decoupled Out-of-Band Policy Engine with Cryptographic Passports.**

### Implementation Blueprint
1. **Policy Decision Point (PDP)**: Eunomia runs as an independent daemon (Docker / PyPI) exposing `/admin/policies` (ABAC configuration) and `/auth/passport/issue`.
2. **Session Bootstrap**: When an agent session initializes, it presents credentials and session context to Eunomia. Eunomia issues an ed25519-signed **Agent Passport** with a time-to-live (TTL) and granular tool execution scopes.
3. **Policy Enforcement Point (PEP)**: An MCP client middleware intercepts all `tools/call` requests. 
   - Non-state-mutating, low-risk tools are verified locally against passport claim signatures.
   - High-risk state mutations (e.g., database writes, network egress) trigger an asynchronous `/check` verification request to Eunomia before execution proceeds.

---

## What Would Change This Decision

If the hackathon runtime constraints restrict custom MCP middleware integration inside the agent harness, necessitating a zero-code-change drop-in HTTP proxy layer. (Current Apertus harness architecture fully supports MCP client middleware, confirming this decision).

---

## Related Documents
- [[ADR-002 — Agent Passport Schema & Cantonal Jurisdiction Claims]]
- [[ADR-003 — Event-Sourced Agent Ledger & CQRS Audit Model]]
- [[Swiss AI Hackathon — Apertus]]
