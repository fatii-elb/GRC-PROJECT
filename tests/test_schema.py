"""
tests/test_schema.py

Automated tests for the shared data contract (scanner/schema.py).
Every guarantee we validated by hand in the terminal during the schema
review is captured here, permanently, so it's checked on every future
change instead of only once.
"""
from uuid import uuid4

import pytest
from pydantic import ValidationError

from scanner.schema import (
    ComplianceScore,
    Domain,
    EnrichedFinding,
    Finding,
    FinancialRiskAssessment,
    FindingStatus,
    NormalizedResource,
    RegulatoryCitation,
)


# ---------------------------------------------------------------------------
# Fixtures — small, reusable, valid objects to build tests on top of
# ---------------------------------------------------------------------------

@pytest.fixture
def finding() -> Finding:
    return Finding(
        cloud_provider="gcp",
        resource_id="bucket-1",
        resource_type="storage_bucket",
        rule_id="storage.encryption_disabled",
        domain="storage",
        severity="high",
        description="Bucket is not encrypted at rest.",
    )


@pytest.fixture
def citation() -> RegulatoryCitation:
    return RegulatoryCitation(
        framework="ISO 27001",
        article_or_control="A.8.24",
        excerpt="Cryptographic controls shall be used to protect information.",
        source_document_id="iso27001-2022",
    )


# ---------------------------------------------------------------------------
# NormalizedResource
# ---------------------------------------------------------------------------

class TestNormalizedResource:
    def test_valid_resource_is_accepted(self):
        r = NormalizedResource(
            cloud_provider="gcp",
            resource_type="storage_bucket",
            resource_id="bucket-1",
            raw_data={"name": "bucket-1"},
        )
        assert r.cloud_provider == "gcp"
        assert r.region is None  # optional field, not provided

    def test_invalid_cloud_provider_is_rejected(self):
        with pytest.raises(ValidationError):
            NormalizedResource(
                cloud_provider="Gcp",  # wrong casing
                resource_type="storage_bucket",
                resource_id="bucket-1",
                raw_data={},
            )

    def test_blank_resource_id_is_rejected(self):
        with pytest.raises(ValidationError):
            NormalizedResource(
                cloud_provider="gcp", resource_type="storage_bucket", resource_id="   ", raw_data={}
            )

    def test_unexpected_field_is_rejected(self):
        with pytest.raises(ValidationError):
            NormalizedResource(
                cloud_provider="gcp",
                resource_type="x",
                resource_id="y",
                raw_data={},
                not_a_real_field="oops",
            )

    def test_oversized_raw_data_is_rejected(self):
        with pytest.raises(ValidationError):
            NormalizedResource(
                cloud_provider="gcp",
                resource_type="x",
                resource_id="y",
                raw_data={"blob": "x" * 200_000},
            )

    def test_is_frozen(self):
        r = NormalizedResource(cloud_provider="gcp", resource_type="x", resource_id="y", raw_data={})
        with pytest.raises(ValidationError):
            r.resource_id = "changed"

    def test_raw_data_excluded_from_repr(self):
        r = NormalizedResource(
            cloud_provider="gcp", resource_type="x", resource_id="y", raw_data={"secret": "sh0uldn0tleak"}
        )
        assert "sh0uldn0tleak" not in repr(r)


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------

class TestFinding:
    def test_defaults_to_open_status(self, finding):
        assert finding.status == FindingStatus.OPEN

    def test_model_copy_creates_new_object_without_mutating_original(self, finding):
        resolved = finding.model_copy(update={"status": FindingStatus.RESOLVED})
        assert finding.status == FindingStatus.OPEN
        assert resolved.status == FindingStatus.RESOLVED

    def test_is_frozen(self, finding):
        with pytest.raises(ValidationError):
            finding.status = FindingStatus.RESOLVED

    def test_description_over_max_length_is_rejected(self, finding):
        with pytest.raises(ValidationError):
            Finding(
                cloud_provider="gcp",
                resource_id="x",
                resource_type="y",
                rule_id="z",
                domain="storage",
                severity="low",
                description="a" * 2_001,
            )


# ---------------------------------------------------------------------------
# EnrichedFinding
# ---------------------------------------------------------------------------

class TestEnrichedFinding:
    def test_verified_true_without_citations_is_rejected(self, finding):
        with pytest.raises(ValidationError):
            EnrichedFinding(finding=finding, explanation="x", citation_verified=True, citations=[])

    def test_verified_true_with_citation_is_accepted(self, finding, citation):
        ef = EnrichedFinding(finding=finding, explanation="x", citation_verified=True, citations=[citation])
        assert ef.citation_verified is True

    def test_unverified_with_no_citations_is_accepted(self, finding):
        """The 'I don't know' path must remain valid — never force a fake citation."""
        ef = EnrichedFinding(finding=finding, explanation="unsure", citation_verified=False, citations=[])
        assert ef.citations == []


# ---------------------------------------------------------------------------
# FinancialRiskAssessment
# ---------------------------------------------------------------------------

class TestFinancialRiskAssessment:
    def test_valid_range_is_accepted(self):
        fra = FinancialRiskAssessment(
            finding_id=uuid4(), estimated_min_mad=1_000, estimated_max_mad=5_000, rationale="Article 50."
        )
        assert fra.estimated_max_mad >= fra.estimated_min_mad

    def test_max_below_min_is_rejected(self):
        with pytest.raises(ValidationError):
            FinancialRiskAssessment(
                finding_id=uuid4(), estimated_min_mad=5_000, estimated_max_mad=1_000, rationale="x"
            )

    def test_negative_amount_is_rejected(self):
        with pytest.raises(ValidationError):
            FinancialRiskAssessment(finding_id=uuid4(), estimated_min_mad=-1, estimated_max_mad=100, rationale="x")


# ---------------------------------------------------------------------------
# ComplianceScore — Enum-keyed dict serialization
# ---------------------------------------------------------------------------

class TestComplianceScore:
    def test_score_within_bounds_is_accepted(self):
        cs = ComplianceScore(overall_score=82.5, total_findings=10, critical_findings=2)
        assert 0 <= cs.overall_score <= 100

    def test_score_over_100_is_rejected(self):
        with pytest.raises(ValidationError):
            ComplianceScore(overall_score=101, total_findings=1, critical_findings=0)

    def test_enum_keys_serialize_to_plain_strings_in_json_mode(self):
        cs = ComplianceScore(
            overall_score=80, total_findings=5, critical_findings=1, score_by_domain={Domain.STORAGE: 90.0}
        )
        dumped = cs.model_dump(mode="json")
        assert list(dumped["score_by_domain"].keys()) == ["storage"]
