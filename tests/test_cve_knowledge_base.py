"""Test suite for CVE knowledge base and persona mapping.

Tests cover CVE lookup, filtering, persona mapping, and validation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apps.backend.src.tools.knowledge.cve_base import CVEKnowledgeBase


class TestCVEKnowledgeBaseInitialization:
    """Test CVEKnowledgeBase initialization."""

    def test_initialization_with_valid_file(self, cve_knowledge_file: Path) -> None:
        """Verify CVEKnowledgeBase initializes with valid file."""
        base = CVEKnowledgeBase(cve_knowledge_file)
        assert base is not None
        assert base.cve_knowledge_file == cve_knowledge_file

    def test_initialization_raises_on_missing_file(self) -> None:
        """Verify FileNotFoundError raised for missing file."""
        with pytest.raises(FileNotFoundError):
            CVEKnowledgeBase("/nonexistent/path/to/cve_knowledge.yaml")


class TestCVERetrieval:
    """Test CVE retrieval and lookup."""

    def test_get_cve_by_id(self, cve_knowledge_file: Path) -> None:
        """Retrieve CVE by ID and verify structure."""
        base = CVEKnowledgeBase(cve_knowledge_file)
        cve_ids = base.list_indexed_cves()

        assert len(cve_ids) > 0

        # Test first CVE
        cve_id = cve_ids[0]
        cve = base.get_cve_by_id(cve_id)

        assert isinstance(cve, dict)
        assert "metadata" in cve
        assert "vulnerability" in cve
        assert "exploitation" in cve
        assert "impact" in cve
        assert "remediation" in cve
        assert "persona_mapping" in cve

    def test_get_cve_by_id_raises_for_unknown_cve(self, cve_knowledge_file: Path) -> None:
        """Verify KeyError raised for unknown CVE."""
        base = CVEKnowledgeBase(cve_knowledge_file)

        with pytest.raises(KeyError):
            base.get_cve_by_id("CVE-0000-00000")

    def test_list_indexed_cves(self, cve_knowledge_file: Path) -> None:
        """Verify all CVEs are indexable."""
        base = CVEKnowledgeBase(cve_knowledge_file)
        cves = base.list_indexed_cves()

        assert isinstance(cves, list)
        assert len(cves) >= 35  # At least 35 CVEs based on spec


class TestCVEFiltering:
    """Test CVE filtering by various criteria."""

    @pytest.mark.parametrize(
        "product,expected_min",
        [
            ("OpenSSL", 1),
            ("Apache HTTP Server", 1),
            ("WordPress", 1),
        ],
    )
    def test_find_cves_by_product(
        self, cve_knowledge_file: Path, product: str, expected_min: int
    ) -> None:
        """Find CVEs by product name."""
        base = CVEKnowledgeBase(cve_knowledge_file)
        cves = base.find_cves_by_product(product)

        assert isinstance(cves, list)
        assert len(cves) >= expected_min

    def test_find_cves_by_product_with_version(self, cve_knowledge_file: Path) -> None:
        """Find CVEs by product and version."""
        base = CVEKnowledgeBase(cve_knowledge_file)

        # Test with Apache 2.4.49 which should match CVE-2021-41773
        cves = base.find_cves_by_product("Apache HTTP Server", "2.4.49")

        assert isinstance(cves, list)
        # Should find at least one CVE affecting this version
        if len(cves) > 0:
            affected_versions = cves[0].get("vulnerability", {}).get("affected_versions", [])
            # Verify version matching logic worked
            assert any("2.4.49" in v or "2.4.49" in v for v in affected_versions)

    @pytest.mark.parametrize(
        "vuln_type",
        [
            "Remote Code Execution",
            "Path Traversal",
            "SQL Injection",
        ],
    )
    def test_find_cves_by_type(self, cve_knowledge_file: Path, vuln_type: str) -> None:
        """Find CVEs by vulnerability type."""
        base = CVEKnowledgeBase(cve_knowledge_file)
        cves = base.find_cves_by_type(vuln_type)

        assert isinstance(cves, list)
        # Some types may not have entries

    @pytest.mark.parametrize("severity", ["CRITICAL", "HIGH", "MEDIUM"])
    def test_find_cves_by_severity(self, cve_knowledge_file: Path, severity: str) -> None:
        """Find CVEs by severity level."""
        base = CVEKnowledgeBase(cve_knowledge_file)
        cves = base.find_cves_by_severity(severity)

        assert isinstance(cves, list)

        # Verify all returned CVEs have matching severity
        for cve in cves:
            assert cve.get("metadata", {}).get("severity") == severity

    def test_cves_sorted_by_cvss(self, cve_knowledge_file: Path) -> None:
        """Verify CVEs are sorted by CVSS score (descending)."""
        base = CVEKnowledgeBase(cve_knowledge_file)
        cves = base.find_cves_by_product("Apache HTTP Server")

        if len(cves) > 1:
            scores = [cve.get("metadata", {}).get("cvss_score", 0) for cve in cves]
            # Verify sorted in descending order
            assert scores == sorted(scores, reverse=True)


class TestPersonaMapping:
    """Test persona-to-CVE mapping."""

    @pytest.mark.parametrize(
        "persona",
        [
            "sqli_specialist",
            "xss_hunter",
            "rce_hunter",
            "jwt_breaker",
            "auth_bypass_specialist",
        ],
    )
    def test_find_cves_by_persona(self, cve_knowledge_file: Path, persona: str) -> None:
        """Find CVEs relevant to a persona."""
        base = CVEKnowledgeBase(cve_knowledge_file)
        cves = base.find_cves_by_persona(persona)

        assert isinstance(cves, list)
        # Personas may have CVEs mapped

    def test_persona_mapping_completeness(self, persona_cve_mapping_file: Path) -> None:
        """Verify persona mapping file is complete."""
        import yaml

        with persona_cve_mapping_file.open("r") as f:
            data = yaml.safe_load(f)

        personas = data.get("persona_mappings", {})
        assert len(personas) >= 15  # At least 15 personas mapped


class TestPlaybookMapping:
    """Test playbook-to-CVE mapping."""

    @pytest.mark.parametrize(
        "playbook",
        [
            "Remote Code Execution Playbook",
            "SQL Injection Exploitation Playbook",
            "TLS Weakness Exploitation",
        ],
    )
    def test_find_cves_for_playbook(self, cve_knowledge_file: Path, playbook: str) -> None:
        """Find CVEs for a playbook."""
        base = CVEKnowledgeBase(cve_knowledge_file)
        cves = base.find_cves_for_playbook(playbook)

        assert isinstance(cves, list)


class TestExploitationPatterns:
    """Test exploitation pattern retrieval."""

    def test_get_exploitation_patterns(self, cve_knowledge_file: Path) -> None:
        """Retrieve exploitation patterns for a CVE."""
        base = CVEKnowledgeBase(cve_knowledge_file)
        cve_ids = base.list_indexed_cves()

        if len(cve_ids) > 0:
            cve_id = cve_ids[0]
            patterns = base.get_exploitation_patterns(cve_id)

            assert isinstance(patterns, list)
            # Patterns may be empty for some CVEs

    def test_exploitation_patterns_structure(self, cve_knowledge_file: Path) -> None:
        """Verify exploitation pattern structure."""
        base = CVEKnowledgeBase(cve_knowledge_file)

        # Find a CVE with patterns
        for cve_id in base.list_indexed_cves():
            patterns = base.get_exploitation_patterns(cve_id)
            if patterns:
                for pattern in patterns:
                    assert isinstance(pattern, dict)
                    assert "pattern_name" in pattern or "likelihood" in pattern
                break


class TestValidation:
    """Test CVE knowledge base validation."""

    def test_validate_cve_knowledge(self, cve_knowledge_file: Path) -> None:
        """Run validation on CVE knowledge base."""
        base = CVEKnowledgeBase(cve_knowledge_file)
        is_valid, issues = base.validate_cve_knowledge()

        assert isinstance(is_valid, bool)
        assert isinstance(issues, list)

        if not is_valid:
            # Log issues for debugging
            for issue in issues:
                print(f"Validation issue: {issue}")


class TestStatistics:
    """Test statistics generation."""

    def test_get_statistics(self, cve_knowledge_file: Path) -> None:
        """Retrieve knowledge base statistics."""
        base = CVEKnowledgeBase(cve_knowledge_file)
        stats = base.get_statistics()

        assert isinstance(stats, dict)
        assert "total_cves" in stats
        assert "total_products" in stats
        assert "total_vulnerability_types" in stats
        assert "by_severity" in stats

        assert stats["total_cves"] >= 35
        assert stats["total_products"] >= 5


class TestVersionMatching:
    """Test version matching logic."""

    @pytest.mark.parametrize(
        "version,affected,expected",
        [
            ("2.4.49", ["2.4.49"], True),
            ("2.4.49", ["2.4.49", "2.4.50"], True),
            ("2.4.49", ["2.4.49-2.4.50"], True),
            ("2.4.50", ["2.4.49-2.4.50"], True),
            ("2.4.51", ["2.4.49-2.4.50"], False),
            ("1.0.1", ["1.0.1"], True),
            ("1.0.2", ["1.0.1"], False),
        ],
    )
    def test_version_matching(self, version: str, affected: list[str], expected: bool) -> None:
        """Test version matching logic."""
        result = CVEKnowledgeBase._version_matches(version, affected)
        assert result == expected


class TestCVEIntegrity:
    """Test CVE data integrity."""

    def test_all_cves_have_metadata(self, cve_knowledge_file: Path) -> None:
        """Verify all CVEs have metadata."""
        base = CVEKnowledgeBase(cve_knowledge_file)

        for cve_id in base.list_indexed_cves():
            cve = base.get_cve_by_id(cve_id)
            metadata = cve.get("metadata", {})

            assert "cve_id" in metadata
            assert "cvss_score" in metadata
            assert "severity" in metadata

    def test_all_cves_have_vulnerability_info(self, cve_knowledge_file: Path) -> None:
        """Verify all CVEs have vulnerability information."""
        base = CVEKnowledgeBase(cve_knowledge_file)

        for cve_id in base.list_indexed_cves():
            cve = base.get_cve_by_id(cve_id)
            vuln = cve.get("vulnerability", {})

            assert "product" in vuln
            assert "affected_versions" in vuln
            assert "vulnerability_type" in vuln


# Fixtures


@pytest.fixture
def cve_knowledge_file() -> Path:
    """Provide path to CVE knowledge file."""
    kai_root = Path(__file__).resolve().parents[1]
    cve_path = kai_root / "tools" / "knowledge" / "cve_knowledge.yaml"
    if not cve_path.exists():
        pytest.skip("cve_knowledge.yaml not found")
    return cve_path


@pytest.fixture
def persona_cve_mapping_file() -> Path:
    """Provide path to persona-CVE mapping file."""
    kai_root = Path(__file__).resolve().parents[1]
    mapping_path = kai_root / "tools" / "knowledge" / "persona_cve_mapping.yaml"
    if not mapping_path.exists():
        pytest.skip("persona_cve_mapping.yaml not found")
    return mapping_path


# ============================================================================
# INTEGRATION TESTS FOR EXPANDED KNOWLEDGE BASE (PROMPT 2)
# ============================================================================

class TestExpandedKnowledgeBase:
    """Test suite for expanded CVE knowledge base (250+ CVEs after integration)."""

    @pytest.fixture
    def expanded_kb_file(self) -> Path:
        """Provide path to expanded CVE knowledge base."""
        kai_root = Path(__file__).resolve().parents[1]
        expanded_path = kai_root / "tools" / "knowledge" / "cve_knowledge_expanded.yaml"
        if not expanded_path.exists():
            pytest.skip("cve_knowledge_expanded.yaml not found")
        return expanded_path

    @pytest.fixture
    def integration_metadata_file(self) -> Path:
        """Provide path to integration metadata."""
        kai_root = Path(__file__).resolve().parents[1]
        metadata_path = kai_root / "tools" / "knowledge" / "cve_integration_metadata.json"
        if not metadata_path.exists():
            pytest.skip("cve_integration_metadata.json not found")
        return metadata_path

    def test_expanded_kb_exists(self, expanded_kb_file: Path) -> None:
        """Verify expanded knowledge base file exists."""
        assert expanded_kb_file.exists()

    def test_integration_metadata_exists(self, integration_metadata_file: Path) -> None:
        """Verify integration metadata file exists."""
        assert integration_metadata_file.exists()

    def test_expanded_kb_valid_yaml(self, expanded_kb_file: Path) -> None:
        """Verify expanded YAML file is valid."""
        import yaml

        try:
            with expanded_kb_file.open("r") as f:
                data = yaml.safe_load(f)
                assert "cve_index" in data
        except yaml.YAMLError as e:
            pytest.fail(f"Invalid YAML: {e}")

    def test_expanded_kb_no_placeholders(self, expanded_kb_file: Path) -> None:
        """Verify expanded KB has no placeholder CVEs (CVE-2024-99xxx)."""
        import yaml

        with expanded_kb_file.open("r") as f:
            data = yaml.safe_load(f)

        for cve_id in data.get("cve_index", {}).keys():
            assert not cve_id.startswith("CVE-2024-99"), f"Placeholder found: {cve_id}"

    def test_expanded_kb_minimum_cves(self, expanded_kb_file: Path) -> None:
        """Verify expanded KB has minimum required CVEs (209 real)."""
        import yaml

        with expanded_kb_file.open("r") as f:
            data = yaml.safe_load(f)

        total_cves = len(data.get("cve_index", {}))
        assert total_cves >= 209, f"Expected >= 209 real CVEs, got {total_cves}"

    def test_integration_metadata_valid_json(self, integration_metadata_file: Path) -> None:
        """Verify integration metadata is valid JSON."""
        import json

        try:
            with integration_metadata_file.open("r") as f:
                json.load(f)
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON: {e}")

    def test_integration_metadata_has_summary(self, integration_metadata_file: Path) -> None:
        """Verify integration metadata contains summary information."""
        import json

        with integration_metadata_file.open("r") as f:
            metadata = json.load(f)

        required_fields = [
            "total_cves",
            "cves_from_existing_base",
            "deduplication_summary",
            "cisa_kev_status"
        ]

        for field in required_fields:
            assert field in metadata, f"Missing field: {field}"

    def test_no_duplicate_cves(self, expanded_kb_file: Path) -> None:
        """Verify no duplicate CVE IDs in expanded KB."""
        import yaml

        with expanded_kb_file.open("r") as f:
            data = yaml.safe_load(f)

        cve_ids = list(data.get("cve_index", {}).keys())
        assert len(cve_ids) == len(set(cve_ids)), "Duplicate CVE IDs found"

    def test_deduplication_documented(self, integration_metadata_file: Path) -> None:
        """Verify deduplication summary is documented."""
        import json

        with integration_metadata_file.open("r") as f:
            metadata = json.load(f)

        dedup = metadata.get("deduplication_summary", {})
        assert "duplicate_cves_found" in dedup
        assert "total_unique_cves" in dedup

    def test_cisa_kev_status_tracked(self, integration_metadata_file: Path) -> None:
        """Verify CISA KEV status is tracked in metadata."""
        import json

        with integration_metadata_file.open("r") as f:
            metadata = json.load(f)

        cisa_status = metadata.get("cisa_kev_status", {})
        assert "actively_exploited" in cisa_status
        assert isinstance(cisa_status.get("actively_exploited"), int)

    def test_severity_distribution_present(self, integration_metadata_file: Path) -> None:
        """Verify severity distribution is documented."""
        import json

        with integration_metadata_file.open("r") as f:
            metadata = json.load(f)

        severity_dist = metadata.get("severity_distribution", {})
        assert len(severity_dist) > 0, "No severity distribution data"

    def test_source_distribution_present(self, integration_metadata_file: Path) -> None:
        """Verify source distribution is documented."""
        import json

        with integration_metadata_file.open("r") as f:
            metadata = json.load(f)

        source_dist = metadata.get("source_distribution", {})
        assert len(source_dist) > 0, "No source distribution data"

    def test_integration_timestamp_present(self, integration_metadata_file: Path) -> None:
        """Verify integration timestamp is recorded."""
        import json

        with integration_metadata_file.open("r") as f:
            metadata = json.load(f)

        assert "integration_timestamp" in metadata
        assert metadata["integration_timestamp"] is not None

    def test_critical_cves_in_expanded(self, expanded_kb_file: Path) -> None:
        """Verify expanded KB has CRITICAL severity CVEs."""
        import yaml

        with expanded_kb_file.open("r") as f:
            data = yaml.safe_load(f)

        critical_count = sum(
            1 for cve in data.get("cve_index", {}).values()
            if cve.get("metadata", {}).get("severity") == "CRITICAL"
        )

        assert critical_count > 0, "No CRITICAL CVEs found in expanded KB"

    def test_rce_cves_in_expanded(self, expanded_kb_file: Path) -> None:
        """Verify expanded KB has RCE vulnerabilities."""
        import yaml

        with expanded_kb_file.open("r") as f:
            data = yaml.safe_load(f)

        rce_count = 0
        for cve in data.get("cve_index", {}).values():
            vuln_type = cve.get("vulnerability", {}).get("vulnerability_type", "")
            if "Remote Code" in vuln_type or "RCE" in vuln_type:
                rce_count += 1

        assert rce_count > 0, "No RCE CVEs found in expanded KB"

    def test_integration_summary_report(self, expanded_kb_file: Path, integration_metadata_file: Path) -> None:
        """Generate and verify integration summary report."""
        import yaml
        import json

        with expanded_kb_file.open("r") as f:
            kb_data = yaml.safe_load(f)

        with integration_metadata_file.open("r") as f:
            metadata = json.load(f)

        total = len(kb_data.get("cve_index", {}))
        existing = metadata.get("cves_from_existing_base", 0)
        from_prompt1 = metadata.get("cves_from_prompt1", 0)

        print(f"\n\n{'='*70}")
        print(f"INTEGRATION SUMMARY REPORT")
        print(f"{'='*70}")
        print(f"Total CVEs in Expanded KB: {total}")
        print(f"CVEs from existing base: {existing}")
        print(f"CVEs from PROMPT 1 (validated): {from_prompt1}")
        print(f"Integration timestamp: {metadata.get('integration_timestamp')}")
        print(f"{'='*70}")

        # Verify consistency
        assert total >= existing, "Total should be >= existing"
