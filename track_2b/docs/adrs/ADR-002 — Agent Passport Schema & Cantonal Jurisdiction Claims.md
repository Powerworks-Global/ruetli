# ADR-002: Agent Passport Schema & Cantonal Sovereign Jurisdiction Claims

**Status:** Accepted  
**Date:** 2026-10-03  
**Deciders:** William Power  
**Project:** Swiss AI Hackathon — Apertus 1.5 (Shared Core for Auditor & Sovereign Mesh)  

---

## Context

In regulated Swiss public administration and financial services, authorization cannot be reduced to a generic OAuth2 `role: admin` or a static bearer token. 

Under the **Swiss Federal Act on Data Protection (FADP)**, the **FINMA Circulars**, and cantonal data sovereignty structures, agent execution must respect three distinct operational constraints:
1. **Federal vs. Cantonal Boundaries**: An agent authorized to process tax filings in the Canton of Zurich (`CHE-ZH`) must have zero authority to query health records in Geneva (`CHE-GE`).
2. **Data Classification Ceiling**: Agents must have an immutable ceiling on the sensitivity of data they are cleared to inspect or mutate (`PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `SECRET`).
3. **Agent Delegation Lineage**: In multi-agent pipelines, a child subagent must inherit a strictly down-scoped subset of its parent agent's privileges, preventing privilege escalation.

---

## Decision Drivers

- **Swiss Cantonal Sovereignty**: Clear cryptographic assertion of cantonal jurisdiction to satisfy public sector stakeholders (e.g. Dr. Benedikt van Spyk).
- **Least-Privilege Tool Scoping**: Defining deterministic glob/regex whitelist patterns for Model Context Protocol (MCP) tools.
- **Cryptographic Verification Overhead**: The token format must be compact, fast to decode at edge (Python / TypeScript / Rust), and signed with tamper-evident modern cryptography (ed25519).
- **Traceability to Human Principal**: Every automated action must resolve to an authenticated natural person or legal entity to comply with EU AI Act Article 14 (Human Oversight).

---

## Considered Options

| Option | Token Shape | Strengths | Weaknesses |
| :--- | :--- | :--- | :--- |
| **Option A: Generic OAuth2 Bearer Token** | JWT (`scope: "mcp:tools"`) | Standard web tooling, simple parser. | Lacks cantonal jurisdiction, data classification ceiling, and agent delegation lineage. |
| **Option B: Full W3C Verifiable Credential** | JSON-LD + Linked Data Signatures | Highly expressive semantic web standard. | Heavy payload, parsing latency, complex schema resolution dependencies on edge. |
| **Option C: Compact Cryptographic Agent Passport (Chosen)** | Signed JSON Web Token (JWT/CBOR) with ed25519 signature & strict domain claims | Fast decoding, self-contained, encodes Swiss jurisdiction, classification ceilings, and tool patterns. | Requires custom claim validator in PEP middleware. |

---

## Decision Outcome

**We choose Option C: Compact Cryptographic Agent Passport.**

Eunomia issues an ed25519-signed JSON token with the following schema:

```json
{
  "header": {
    "alg": "EdDSA",
    "typ": "EUNOMIA-AGENT-PASSPORT-V1"
  },
  "payload": {
    "jti": "pass_9f83a2c0-e4b2-4d2b-91d8-77b3b4f62091",
    "iss": "https://auth.eunomia.swiss",
    "sub": "user:william.power@powerworks.global",
    "aud": "apertus-agent-mesh",
    "iat": 1788620000,
    "exp": 1788623600,
    
    "agent_context": {
      "agent_id": "agent_auditor_01",
      "parent_agent_id": null,
      "session_id": "sess_478999",
      "harness": "apertus-1.5"
    },

    "jurisdiction": {
      "country": "CHE",
      "canton": "CHE-ZH",
      "regulatory_regime": ["SWISS_FADP", "EU_AI_ACT_ANNEX_III", "FINMA_CIRC_2023_01"]
    },

    "security_profile": {
      "classification_ceiling": "CONFIDENTIAL",
      "allow_cloud_egress": true,
      "allowed_egress_endpoints": ["https://api.cscs.ch/apertus/v1"]
    },

    "mcp_tool_authorizations": {
      "allowed_tools": [
        "cantonal_tax_db:get_statute",
        "cantonal_tax_db:validate_deduction",
        "filesystem:read_workspace"
      ],
      "denied_tools": [
        "cantonal_tax_db:delete_*",
        "network:raw_socket",
        "shell:execute_bash"
      ]
    }
  }
}
```

### Claim Definitions & Invariants
1. **`jurisdiction.canton`**: Enforces location-bound data access. The MCP interceptor denies any tool invocation targeting a mismatched cantonal database.
2. **`security_profile.classification_ceiling`**: If a query detects `SECRET` data attributes, tool execution immediately halts regardless of tool permissions.
3. **`mcp_tool_authorizations`**: Explicit allowlist and denylist patterns evaluated using first-match-deny precedence before the tool is executed.

---

## What Would Change This Decision

If the Swiss Federal Administration establishes an official electronic identity wallet (EUDI / Swiss E-ID) credential format for automated software agents, the payload claims will be mapped directly into that verifiable credential profile.

---

## Related Documents
- [[ADR-001 — Decoupled Policy Engine over Synchronous Proxy]]
- [[ADR-003 — Event-Sourced Agent Ledger & CQRS Audit Model]]
- [[ADR-004 — Deterministic Edge Tokenization with Local Reconstitution]]
