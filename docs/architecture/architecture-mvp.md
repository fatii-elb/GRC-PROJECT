# Architecture Decision Record — MVP Data Contract

**Status:** Accepted — Milestone 1
**Owners:** Student A & Student B (joint)
**Schema version:** 1.1.0 (see `scanner/schema.py`)

## Why normalization matters here

AWS, Azure, and GCP each shape their configuration data differently — an IAM
policy binding in GCP looks nothing like an IAM policy document in AWS or a
role assignment in Azure. Without a single, agreed shape, every downstream
component (the rule engine, the API, the dashboard) would need a separate
code path per cloud provider. `NormalizedResource` is the one shape all three
connectors translate into, so everything built on top of it — including
components neither of us has written yet — only ever needs to understand one
data model, not three.

## What's in the contract today

| Model | Produced by | Consumed by |
|---|---|---|
| `NormalizedResource` | Cloud connectors (AWS/Azure/GCP) | Rule engine only — **never exposed via the API** |
| `Finding` | Rule engine | Backend API, AI copilot, risk translator |
| `RegulatoryCitation` | AI copilot (citation checker) | `EnrichedFinding`, `FinancialRiskAssessment` |
| `EnrichedFinding` | AI copilot / finding linker | Backend API, dashboard |
| `FinancialRiskAssessment` | Financial risk translator | Backend API, dashboard |
| `ComplianceScore` | Scoring aggregation | Backend API, dashboard |

**Why `NormalizedResource` never leaves the backend:** it's raw, per-provider
scan output — useful to the rule engine, not to a human. The frontend only
ever needs to know about *findings* (what's wrong) and *scores* (how bad),
never the raw resource dump that produced them. Keeping it out of
`openapi.yaml` keeps the public API surface smaller and easier to reason
about.

## Why every model is immutable (`frozen=True`)

This is a compliance/audit tool. "A finding was silently modified in memory
and nobody can say when or why" is a worse failure mode here than in most
software. Every model in `schema.py` is frozen — legitimate state changes
(e.g. a finding moving from `OPEN` to `RESOLVED`) happen via
`finding.model_copy(update={"status": FindingStatus.RESOLVED})`, which
produces a new, explicit object rather than mutating the old one in place.

This is a deliberate trade-off: slightly more verbose updates, in exchange
for every state change being explicit and traceable. We judged this worth it
specifically because of the compliance/audit context — a general-purpose
CRUD app might reasonably choose otherwise.

**Known limitation, stated honestly:** `frozen=True` prevents reassigning a
field (`finding.status = ...` raises), but does not deep-freeze nested
containers (`finding.tags["x"] = "y"` would still succeed). Full deep
immutability was judged not worth the added complexity at this stage.

## Why some fields are strict and others stay open

- `cloud_provider` is a closed `Enum` — a new cloud provider is always a
  deliberate engineering decision (a new connector, new IAM setup), never
  something that should be added by accident via a typo.
- `resource_type` stays a validated, open string — new resource types are
  added constantly as rule coverage grows, and locking it to an `Enum` would
  mean editing this shared file every time either of us adds a check.

## Why `extra="forbid"` everywhere

Every model rejects unexpected fields rather than silently ignoring them.
This is what turns a typo (`resource_Id` instead of `resource_id`) into an
immediate, loud error at construction time, instead of quietly discarded
data that surfaces as a confusing bug three components downstream.

## Size and content guards

`attributes` and `raw_data` on `NormalizedResource` are capped at 100,000
serialized characters, and excluded from the default object `repr()` (and
therefore from default logging). Both guard against the same class of
problem: a buggy or misbehaving connector handing back an unexpectedly large
or sensitive blob that then gets persisted or logged in full.

## What's deliberately not built yet

`CorrelatedRisk`, `ExploitProof`, and `RemediationProposal` are realistic
future directions for this architecture, but are explicitly out of scope for
the current milestone plan. We are not modeling them "for completeness" —
everything in `schema.py` today is consumed by something real.

## Open question for next sync

Should a `/copilot/ask` endpoint (a free-form question, not tied to one
finding) get its own new response model, or should it reuse `EnrichedFinding`
with a nullable `finding` field? Not decided yet — needs a short conversation
before either of us builds it.
