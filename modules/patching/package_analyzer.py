"""Package version analysis and vulnerability detection."""

from typing import Dict, Any, List, Optional, Tuple
from packaging import version


class PackageAnalyzer:
    """Analyze packages and identify vulnerable versions."""

    # Known vulnerable package versions (example data)
    VULNERABLE_PACKAGES = {
        "django": {
            "vulnerable_versions": [
                ("2.0", "2.2.27"),  # Multiple vulnerabilities
                ("3.0", "3.1.13"),  # SQL injection, XSS
                ("3.2", "3.2.12"),  # Path traversal
            ],
            "cves": {
                "2.2.27": ["CVE-2021-33571", "CVE-2021-33574"],
                "3.1.13": ["CVE-2021-33571"],
                "3.2.12": ["CVE-2021-44581"],
            },
        },
        "requests": {
            "vulnerable_versions": [
                ("2.0", "2.6.0"),  # Session fixation
                ("2.7", "2.25.1"),  # Credential exposure
            ],
            "cves": {
                "2.6.0": ["CVE-2018-18074"],
                "2.25.1": ["CVE-2021-33503"],
            },
        },
        "flask": {
            "vulnerable_versions": [
                ("0.10", "0.12.2"),  # XSS in template
                ("1.0", "1.1.2"),  # JSON serialization
            ],
            "cves": {
                "0.12.2": ["CVE-2018-1000656"],
                "1.1.2": ["CVE-2021-21331"],
            },
        },
        "pillow": {
            "vulnerable_versions": [
                ("6.0", "6.2.3"),  # Code execution
                ("7.0", "7.2.0"),  # File upload RCE
                ("8.0", "8.2.0"),  # Buffer overflow
            ],
            "cves": {
                "6.2.3": ["CVE-2021-27921", "CVE-2021-27922"],
                "7.2.0": ["CVE-2021-28675"],
                "8.2.0": ["CVE-2021-28676"],
            },
        },
        "sqlalchemy": {
            "vulnerable_versions": [
                ("1.3", "1.3.24"),  # SQL injection
                ("1.4", "1.4.22"),  # Auth bypass
            ],
            "cves": {
                "1.3.24": ["CVE-2021-32617"],
                "1.4.22": ["CVE-2021-32615"],
            },
        },
    }

    def __init__(self):
        """Initialize package analyzer."""
        self.analyzed_packages: Dict[str, Dict[str, Any]] = {}

    def analyze_package(
        self, package_name: str, current_version: str
    ) -> Dict[str, Any]:
        """
        Analyze a package for vulnerabilities.

        Returns:
            {
                'package': str,
                'current_version': str,
                'is_vulnerable': bool,
                'vulnerability_count': int,
                'cves': [str],
                'recommended_version': str,
                'upgrade_severity': 'critical'|'high'|'medium'|'low',
                'breaking_changes': [str],
                'analysis': {...}
            }
        """
        analysis = {
            "package": package_name,
            "current_version": current_version,
            "is_vulnerable": False,
            "vulnerability_count": 0,
            "cves": [],
            "recommended_version": None,
            "upgrade_severity": "low",
        }

        # Check if package is in vulnerable list
        if package_name not in self.VULNERABLE_PACKAGES:
            analysis["status"] = "not_in_database"
            self.analyzed_packages[package_name] = analysis
            return analysis

        package_info = self.VULNERABLE_PACKAGES[package_name]
        current_ver = version.parse(current_version)

        # Check against vulnerable version ranges
        for start_ver_str, end_ver_str in package_info.get("vulnerable_versions", []):
            start_ver = version.parse(start_ver_str)
            end_ver = version.parse(end_ver_str)

            if start_ver <= current_ver <= end_ver:
                analysis["is_vulnerable"] = True
                cves = package_info.get("cves", {}).get(end_ver_str, [])
                analysis["cves"].extend(cves)
                analysis["vulnerability_count"] += 1

        if analysis["is_vulnerable"]:
            # Find latest safe version (after all vulnerable ranges)
            all_vulnerable = package_info.get("vulnerable_versions", [])
            if all_vulnerable:
                latest_vulnerable = version.parse(all_vulnerable[-1][1])
                # Recommend patch version bump
                analysis["recommended_version"] = str(self._bump_version(latest_vulnerable))
                analysis["upgrade_severity"] = self._assess_upgrade_severity(
                    analysis["vulnerability_count"]
                )

            # Detect potential breaking changes
            analysis["breaking_changes"] = self._detect_breaking_changes(
                package_name, current_version, analysis["recommended_version"]
            )

        analysis["analyzed_at"] = self._current_time()
        self.analyzed_packages[package_name] = analysis
        return analysis

    def analyze_requirements(
        self, requirements: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Analyze all packages in requirements.

        Args:
            requirements: {package_name: version_string}

        Returns:
            {
                'total_packages': int,
                'vulnerable_packages': int,
                'analyses': {...},
                'summary': {...}
            }
        """
        analyses = {}
        vulnerable_count = 0
        total_cves = 0

        for package_name, current_version in requirements.items():
            analysis = self.analyze_package(package_name, current_version)
            analyses[package_name] = analysis

            if analysis.get("is_vulnerable"):
                vulnerable_count += 1
                total_cves += analysis.get("vulnerability_count", 0)

        return {
            "total_packages": len(requirements),
            "vulnerable_packages": vulnerable_count,
            "total_cves": total_cves,
            "vulnerability_ratio": (
                vulnerable_count / len(requirements) if requirements else 0
            ),
            "analyses": analyses,
            "summary": {
                "safe": len(requirements) - vulnerable_count,
                "vulnerable": vulnerable_count,
                "action_required": vulnerable_count > 0,
            },
        }

    def get_upgrade_path(
        self, package_name: str, current_version: str
    ) -> Dict[str, Any]:
        """
        Get recommended upgrade path for a package.

        Returns step-by-step upgrade instructions with testing checkpoints.
        """
        analysis = self.analyze_package(package_name, current_version)

        if not analysis.get("is_vulnerable"):
            return {
                "package": package_name,
                "status": "not_vulnerable",
                "message": f"{package_name} {current_version} is not in vulnerable database",
            }

        recommended = analysis.get("recommended_version")

        upgrade_path = {
            "package": package_name,
            "from_version": current_version,
            "to_version": recommended,
            "steps": [
                {
                    "step": 1,
                    "action": "Review changelog",
                    "description": f"Review changes between {current_version} and {recommended}",
                    "checklist": [
                        "Check for breaking API changes",
                        "Review security fixes",
                        "Check deprecation warnings",
                    ],
                },
                {
                    "step": 2,
                    "action": "Update requirements",
                    "description": f"Update {package_name}=={recommended} in requirements.txt",
                    "command": f"pip install --upgrade {package_name}=={recommended}",
                },
                {
                    "step": 3,
                    "action": "Run tests",
                    "description": "Run all unit and integration tests",
                    "checklist": [
                        "Unit tests pass",
                        "Integration tests pass",
                        "Smoke tests pass",
                        "No new warnings",
                    ],
                },
                {
                    "step": 4,
                    "action": "Deploy to staging",
                    "description": "Deploy updated dependency to staging environment",
                    "checklist": [
                        "Staging deployment successful",
                        "No performance regressions",
                        "Monitor for 24 hours",
                    ],
                },
                {
                    "step": 5,
                    "action": "Deploy to production",
                    "description": "Deploy to production with monitoring",
                    "checklist": [
                        "Production deployment successful",
                        "Monitor error rates",
                        "Check performance metrics",
                        "Verify CVE is fixed",
                    ],
                },
            ],
            "cves_fixed": analysis.get("cves", []),
            "breaking_changes": analysis.get("breaking_changes", []),
            "estimated_time_hours": len(analysis.get("breaking_changes", [])) * 2 + 4,
        }

        return upgrade_path

    def check_cve_status(
        self, package_name: str, current_version: str, cve_id: str
    ) -> Dict[str, Any]:
        """Check if specific CVE is fixed in current version."""
        if package_name not in self.VULNERABLE_PACKAGES:
            return {"cve": cve_id, "status": "unknown", "package": package_name}

        package_info = self.VULNERABLE_PACKAGES[package_name]
        cves_by_version = package_info.get("cves", {})

        # Check if this CVE appears in any vulnerable versions
        is_vulnerable = False
        fixed_in_version = None

        for ver_str, cves in cves_by_version.items():
            if cve_id in cves:
                if version.parse(current_version) <= version.parse(ver_str):
                    is_vulnerable = True
                else:
                    fixed_in_version = ver_str
                    is_vulnerable = False

        return {
            "cve": cve_id,
            "package": package_name,
            "current_version": current_version,
            "status": "fixed" if not is_vulnerable else "vulnerable",
            "fixed_in_version": fixed_in_version,
        }

    def _bump_version(self, ver: Any) -> str:
        """Bump version to next minor/patch."""
        parts = str(ver).split(".")
        if len(parts) >= 2:
            parts[1] = str(int(parts[1]) + 1)
            if len(parts) > 2:
                parts[2] = "0"
        return ".".join(parts)

    def _assess_upgrade_severity(self, vulnerability_count: int) -> str:
        """Assess severity of vulnerabilities."""
        if vulnerability_count >= 5:
            return "critical"
        elif vulnerability_count >= 3:
            return "high"
        elif vulnerability_count >= 1:
            return "medium"
        else:
            return "low"

    def _detect_breaking_changes(
        self, package_name: str, from_version: str, to_version: Optional[str]
    ) -> List[str]:
        """Detect potential breaking changes between versions."""
        if not to_version:
            return []

        breaking_changes = {
            "django": [
                "Django 3.0 removed support for Python 2 and Django 1.11",
                "Django 4.0 removed support for Python 3.6 and 3.7",
            ],
            "flask": [
                "Flask 2.0 changed imports (flask.json is now flask.json.provider)",
                "Flask 2.0 changed default JSONIFY_PRETTYPRINT_REGULAR to False",
            ],
            "sqlalchemy": [
                "SQLAlchemy 1.4 changed the engine API",
                "SQLAlchemy 2.0 requires explicit SQL using sql module",
            ],
        }

        return breaking_changes.get(package_name, [])

    @staticmethod
    def _current_time() -> str:
        """Get current ISO time."""
        from datetime import datetime
        return datetime.utcnow().isoformat()

    def get_analyzer_stats(self) -> Dict[str, Any]:
        """Get statistics on analyzed packages."""
        if not self.analyzed_packages:
            return {
                "total_analyzed": 0,
                "vulnerable": 0,
                "safe": 0,
            }

        vulnerable = sum(
            1 for p in self.analyzed_packages.values() if p.get("is_vulnerable")
        )

        return {
            "total_analyzed": len(self.analyzed_packages),
            "vulnerable": vulnerable,
            "safe": len(self.analyzed_packages) - vulnerable,
            "vulnerability_ratio": vulnerable / len(self.analyzed_packages)
            if self.analyzed_packages
            else 0,
        }
