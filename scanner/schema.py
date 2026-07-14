"""
scanner/schema.py

Copilot GRC Multi-Cloud — Shared Data Contract (Schema Version 1.1.0)
======================================================================

This module is the single source of truth for every data shape that crosses a
boundary in this system: cloud connector -> rule engine -> AI copilot ->
backend API -> dashboard. See docs/architecture/architecture-mvp.md for the
narrative rationale; this docstring covers the technical contract itself.

Immutability policy
--------------------
Every model in this file is frozen (model_config=ConfigDict(frozen=True)).
These objects represent facts that were true at a point in time (a resource's
observed configuration, a detected finding, a computed score) — in an
auditable compliance system, "silently mutated in place" is exactly the class
of bug you cannot afford. To change a value, create a new object explicitly:

    resolved = finding.model_copy(update={"status": FindingStatus.RESOLVED})

This is slightly more verbose than in-place mutation, but it makes every
state change an explicit, greppable, loggable event instead of an invisible
side effect — a worthwhile trade-off for data that may end up in an audit
trail. Note: `frozen=True` prevents *reassigning* a field (e.g.
`finding.status = ...` raises); it does not deep-freeze nested containers
(`finding.tags["x"] = "y"` would still succeed). Full deep immutability was
judged not worth the added complexity for this project's scope.

Ownership & change policy
--------------------------
No field on any model here may be renamed, removed, or have its type narrowed
without a conversation between both developers. Additive, backward-compatible
changes (a new Optional field, a new Enum member) may be made unilaterally
and announced to the team.

Consumers of this module
-------------------------
- scanner/collectors/{aws,azure,gcp}.py  -> produce NormalizedResource
- scanner/engine.py (rule engine)         -> consumes NormalizedResource, produces Finding
- copilot/finding_linker.py               -> enriches Finding -> EnrichedFinding
- scanner/risk_translator.py              -> enriches Finding -> FinancialRiskAssessment
- backend/routes/*.py (FastAPI)           -> serializes all of the above for the frontend
- frontend dashboard                      -> consumes the JSON shapes described here and in openapi.yaml

Serialization note
-------------------
Fields typed as ``dict[Domain, float]`` or ``dict[CloudProvider, float]`` use
an Enum as a dict key. When handed to a *non-Pydantic* consumer (a plain
`json.dumps(...)` call, or a hand-rolled serializer), always export via
`model.model_dump(mode="json")`, never `model.model_dump()` or `dict(model)`
— only "json" mode is guaranteed to turn those Enum keys into plain strings.
"""

from __future__ import annotations

__all__ = [
    "SCHEMA_VERSION",
    "CloudProvider",
    "Severity",
    "Domain",
    "FindingStatus",
    "NonBlankStr",
    "NormalizedResource",
    "Finding",
    "RegulatoryCitation",
    "EnrichedFinding",
    "FinancialRiskAssessment",
    "ComplianceScore",
]

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Optional
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from typing_extensions import Self

SCHEMA_VERSION = "1.1.0"

# Shared, module-level guard against a buggy/malicious connector returning an
# unbounded payload (e.g. a misconfigured API pagination loop). Cheap to
# check, expensive to discover after it's already bloated a database row.
_MAX_RAW_PAYLOAD_CHARS = 100_000


# ---------------------------------------------------------------------------
# Reusable validated types
# ---------------------------------------------------------------------------

def _not_blank(v: str) -> str:
    if not v.strip():
        raise ValueError("must not be empty or whitespace-only")
    return v


NonBlankStr = Annotated[str, AfterValidator(_not_blank)]
"""A str guaranteed non-empty after stripping whitespace. Defined once, reused
on every identifier-like field below, instead of repeating the same
field_validator on each model."""


def _bounded_payload(v: dict[str, Any]) -> dict[str, Any]:
    size = len(json.dumps(v, default=str))
    if size > _MAX_RAW_PAYLOAD_CHARS:
        raise ValueError(
            f"payload is {size} characters, exceeding the {_MAX_RAW_PAYLOAD_CHARS}-character "
            "limit — check the upstream connector for a pagination or serialization bug"
        )
    return v


BoundedPayload = Annotated[dict[str, Any], AfterValidator(_bounded_payload)]
"""A dict[str, Any] with a hard size ceiling — see _MAX_RAW_PAYLOAD_CHARS."""


# ---------------------------------------------------------------------------
# Enums — closed vocabularies shared across the whole system
# ---------------------------------------------------------------------------

class CloudProvider(str, Enum):
    """Which cloud a resource or finding originated from.

    Deliberately a closed Enum, not an open string: this project only ever
    onboards a new cloud provider through a deliberate engineering decision
    (a new connector module, new IAM setup, new rule mappings) — never by
    accident. A typo here should fail loudly, not silently create a fourth
    "cloud" that nothing else in the system recognizes.
    """

    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"


class Severity(str, Enum):
    """Compliance severity, ordered low -> critical."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Domain(str, Enum):
    """Rule domain. Also used to route findings to the correct dashboard tab
    and to the correct developer's rule-engine ownership (IAM/network vs.
    encryption/logging/storage)."""

    IAM = "iam"
    NETWORK = "network"
    ENCRYPTION = "encryption"
    LOGGING = "logging"
    STORAGE = "storage"


class FindingStatus(str, Enum):
    """Lifecycle status of a finding. Deliberately small — see 'Future
    extension points' at the end of this file for why a richer workflow
    model is not included yet."""

    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


# ---------------------------------------------------------------------------
# 1. NormalizedResource — output of every cloud connector
# ---------------------------------------------------------------------------

class NormalizedResource(BaseModel):
    """A single cloud resource, in a shape that hides which provider it came
    from. Immutable: this is a point-in-time snapshot of what a connector
    observed, not a live-updating object.

    This is the most foundational model in the whole system: every rule,
    every score, every dashboard view is ultimately downstream of this shape
    staying consistent across AWS, Azure, and GCP.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    cloud_provider: CloudProvider
    resource_type: NonBlankStr = Field(
        ...,
        description=(
            "Open-ended on purpose (e.g. 'storage_bucket', 'iam_binding', "
            "'firewall_rule'). New resource types are added constantly as "
            "rule coverage grows; locking this to an Enum would require "
            "editing this shared file every time either developer adds a "
            "new check."
        ),
    )
    resource_id: NonBlankStr = Field(
        ..., description="Unique identifier within the resource's own cloud provider."
    )
    region: Optional[str] = Field(
        default=None, description="Not every resource has one (e.g. an IAM binding is global)."
    )
    tags: dict[str, str] = Field(default_factory=dict, description="Cloud-native tags/labels, if any.")
    attributes: BoundedPayload = Field(
        default_factory=dict,
        repr=False,
        description=(
            "Resource-type-specific raw attributes (e.g. encryption flags, "
            "public-access flags). Deliberately untyped: the rule engine "
            "knows which keys to read based on resource_type. Excluded from "
            "repr()/default logging (repr=False) since cloud attributes can "
            "incidentally contain sensitive values."
        ),
    )
    raw_data: BoundedPayload = Field(
        default_factory=dict,
        repr=False,
        description=(
            "The untouched original API response — kept for audit trails and "
            "future AI citation needs. Size-bounded and excluded from "
            "repr()/default logging for the same reasons as `attributes`."
        ),
    )
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("collected_at")
    @classmethod
    def _ensure_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("collected_at must be timezone-aware (use UTC)")
        return v


# ---------------------------------------------------------------------------
# 2. Finding — output of the rule engine
# ---------------------------------------------------------------------------

class Finding(BaseModel):
    """A single compliance problem detected on one resource. Immutable —
    lifecycle transitions (e.g. OPEN -> RESOLVED) are made explicit via
    `finding.model_copy(update={"status": FindingStatus.RESOLVED})`, never
    by mutating an existing object in place."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    id: Optional[UUID] = Field(
        default=None, description="Assigned by the backend/DB on persistence; absent at detection time."
    )
    cloud_provider: CloudProvider
    resource_id: NonBlankStr
    resource_type: NonBlankStr
    rule_id: NonBlankStr = Field(
        ..., description="e.g. 'storage.encryption_disabled', 'network.sg_open_to_world'."
    )
    domain: Domain
    severity: Severity
    description: str = Field(..., min_length=1, max_length=2_000)
    status: FindingStatus = Field(default=FindingStatus.OPEN)
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("detected_at")
    @classmethod
    def _ensure_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("detected_at must be timezone-aware (use UTC)")
        return v


# ---------------------------------------------------------------------------
# 3. RegulatoryCitation & EnrichedFinding — output of the AI copilot
# ---------------------------------------------------------------------------

class RegulatoryCitation(BaseModel):
    """A single, verified citation — never generated without a matching
    source excerpt (see copilot/citation_checker.py)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    framework: NonBlankStr = Field(..., description="e.g. 'ISO 27001', 'Loi 05-20 / DNSSI'.")
    article_or_control: NonBlankStr = Field(..., description="e.g. 'Annex A.8.24', 'Article 12'.")
    excerpt: NonBlankStr = Field(
        ..., max_length=3_000, description="Exact source text — never a paraphrase presented as a quote."
    )
    source_document_id: NonBlankStr


class EnrichedFinding(BaseModel):
    """A Finding enriched with an AI-generated, citation-verified explanation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    finding: Finding
    explanation: str = Field(..., min_length=1, max_length=5_000)
    citations: list[RegulatoryCitation] = Field(default_factory=list)
    citation_verified: bool = Field(
        ...,
        description=(
            "False means the copilot must say 'I don't know' — never guess. "
            "This is enforced as data, not just prompted for."
        ),
    )

    @model_validator(mode="after")
    def _verified_requires_citations(self) -> Self:
        """Makes an invalid state unrepresentable: you cannot claim a
        verified citation while providing zero citations to back it up."""
        if self.citation_verified and not self.citations:
            raise ValueError("citation_verified=True requires at least one citation in `citations`")
        return self


# ---------------------------------------------------------------------------
# 4. FinancialRiskAssessment — output of the financial risk translator
# ---------------------------------------------------------------------------

class FinancialRiskAssessment(BaseModel):
    """Translates a Finding into an estimated sanction exposure, in MAD."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_id: UUID
    estimated_min_mad: float = Field(..., ge=0)
    estimated_max_mad: float = Field(..., ge=0)
    rationale: str = Field(..., min_length=1, max_length=2_000)
    citation: Optional[RegulatoryCitation] = Field(
        default=None,
        description="The article this sanction range is drawn from, if one exists in the corpus.",
    )

    @field_validator("estimated_max_mad")
    @classmethod
    def _max_gte_min(cls, v: float, info) -> float:
        min_val = info.data.get("estimated_min_mad")
        if min_val is not None and v < min_val:
            raise ValueError("estimated_max_mad must be >= estimated_min_mad")
        return v


# ---------------------------------------------------------------------------
# 5. ComplianceScore — final aggregation, consumed by the dashboard
# ---------------------------------------------------------------------------

class ComplianceScore(BaseModel):
    """The single aggregated score object the dashboard renders.

    See the module-level 'Serialization note' — score_by_domain and
    score_by_cloud use Enum keys; always dump with mode="json" for non-
    Pydantic consumers.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    overall_score: float = Field(..., ge=0, le=100)
    score_by_domain: dict[Domain, float] = Field(default_factory=dict)
    score_by_cloud: dict[CloudProvider, float] = Field(default_factory=dict)
    total_findings: int = Field(..., ge=0)
    critical_findings: int = Field(..., ge=0)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Future extension points (documented, deliberately not implemented yet)
# ---------------------------------------------------------------------------
# - CorrelatedRisk: combining multiple Findings into one attack-path narrative.
# - ExploitProof: red-team-style proof of exploitability against the sandbox.
# - RemediationProposal: AI-suggested Terraform fixes, human-approved only.
#
# Also deferred: splitting this single file into a schema/ package
# (enums.py, resources.py, findings.py, ...) once it grows meaningfully past
# its current size. Not done now because the current size doesn't yet
# justify the added navigation overhead of multiple files.
#
# These are realistic next steps for this architecture but are explicitly out
# of scope for the current milestone plan. Keeping them out of this file
# (rather than adding unused models "for completeness") keeps the contract
# honest: everything defined here is actually consumed by something real.
