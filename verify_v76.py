#!/usr/bin/env python3
"""
Kaison K1 Platform v7.6 - Verification Script
Tests all new features and endpoints
"""

import sys
import requests
import json
from typing import Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class Status(Enum):
    PASS = "✓"
    FAIL = "✗"
    SKIP = "○"
    WARN = "⚠"


@dataclass
class TestResult:
    name: str
    status: Status
    message: str = ""

    def __str__(self):
        return f"{self.status.value} {self.name}: {self.message}"


class V76Verifier:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results: List[TestResult] = []

    def test_healthz(self) -> TestResult:
        """Test basic health endpoint"""
        try:
            resp = requests.get(f"{self.base_url}/healthz", timeout=5)
            if resp.status_code == 200 and resp.json().get("ok"):
                return TestResult("Health Check", Status.PASS, "API is responding")
            return TestResult("Health Check", Status.FAIL, f"Status: {resp.status_code}")
        except Exception as e:
            return TestResult("Health Check", Status.FAIL, str(e))

    def test_intelligence_feeds(self) -> TestResult:
        """Test intelligence feeds endpoint"""
        try:
            resp = requests.get(f"{self.base_url}/api/v1/intelligence/feeds", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    feed_count = len(data.get("data", {}).get("feeds", []))
                    return TestResult("Intelligence Feeds", Status.PASS, f"{feed_count} feeds configured")
                return TestResult("Intelligence Feeds", Status.WARN, "No feeds configured")
            return TestResult("Intelligence Feeds", Status.FAIL, f"Status: {resp.status_code}")
        except Exception as e:
            return TestResult("Intelligence Feeds", Status.FAIL, str(e))

    def test_intelligence_stats(self) -> TestResult:
        """Test intelligence statistics endpoint"""
        try:
            resp = requests.get(f"{self.base_url}/api/v1/intelligence/stats", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    stats = data.get("data", {})
                    total = stats.get("total_items", 0)
                    return TestResult("Intelligence Stats", Status.PASS, f"{total} total items")
                return TestResult("Intelligence Stats", Status.WARN, "No statistics available")
            return TestResult("Intelligence Stats", Status.FAIL, f"Status: {resp.status_code}")
        except Exception as e:
            return TestResult("Intelligence Stats", Status.FAIL, str(e))

    def test_notifications_providers(self) -> TestResult:
        """Test notifications providers endpoint"""
        try:
            resp = requests.get(f"{self.base_url}/api/v1/notifications/providers", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    providers = data.get("data", {}).get("providers", [])
                    active = data.get("data", {}).get("active_provider")
                    if active:
                        return TestResult("Notification Providers", Status.PASS, f"Active: {active.get('type')}")
                    return TestResult("Notification Providers", Status.WARN, "No active provider")
                return TestResult("Notification Providers", Status.WARN, "No providers configured")
            return TestResult("Notification Providers", Status.FAIL, f"Status: {resp.status_code}")
        except Exception as e:
            return TestResult("Notification Providers", Status.FAIL, str(e))

    def test_ollama_status(self) -> TestResult:
        """Test Ollama service status"""
        try:
            resp = requests.get(f"{self.base_url}/api/v1/ollama/status", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success") and data.get("data", {}).get("running"):
                    return TestResult("Ollama Service", Status.PASS, "Ollama is running")
                return TestResult("Ollama Service", Status.SKIP, "Ollama not running (optional)")
            return TestResult("Ollama Service", Status.SKIP, "Ollama not configured")
        except Exception as e:
            return TestResult("Ollama Service", Status.SKIP, "Ollama not available (optional)")

    def test_ollama_models(self) -> TestResult:
        """Test Ollama models endpoint"""
        try:
            resp = requests.get(f"{self.base_url}/api/v1/ollama/models", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    models = data.get("data", {}).get("models", [])
                    return TestResult("Ollama Models", Status.PASS, f"{len(models)} models installed")
                return TestResult("Ollama Models", Status.WARN, "No models installed")
            return TestResult("Ollama Models", Status.SKIP, "Ollama not running")
        except Exception as e:
            return TestResult("Ollama Models", Status.SKIP, str(e))

    def test_graph_stats(self) -> TestResult:
        """Test Neo4j graph statistics"""
        try:
            resp = requests.get(f"{self.base_url}/api/v1/graph/stats", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    stats = data.get("data", {})
                    hosts = stats.get("total_hosts", 0)
                    vulns = stats.get("total_vulnerabilities", 0)
                    return TestResult("Graph Database", Status.PASS, f"{hosts} hosts, {vulns} vulns")
                return TestResult("Graph Database", Status.WARN, "No graph data")
            return TestResult("Graph Database", Status.SKIP, "Neo4j not configured (optional)")
        except Exception as e:
            return TestResult("Graph Database", Status.SKIP, "Neo4j not available (optional)")

    def test_orchestrator(self) -> TestResult:
        """Test KaiOrchestrator endpoint"""
        try:
            resp = requests.get(f"{self.base_url}/api/v1/kai/orchestrator/status", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    return TestResult("KaiOrchestrator", Status.PASS, "Orchestrator running")
                return TestResult("KaiOrchestrator", Status.FAIL, "Orchestrator not initialized")
            return TestResult("KaiOrchestrator", Status.FAIL, f"Status: {resp.status_code}")
        except Exception as e:
            return TestResult("KaiOrchestrator", Status.FAIL, str(e))

    def test_watchdog(self) -> TestResult:
        """Test Watchdog service"""
        try:
            resp = requests.get(f"{self.base_url}/api/v1/watchdog/status", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    return TestResult("Log Watchdog", Status.PASS, "Watchdog active")
                return TestResult("Log Watchdog", Status.WARN, "Watchdog not initialized")
            return TestResult("Log Watchdog", Status.FAIL, f"Status: {resp.status_code}")
        except Exception as e:
            return TestResult("Log Watchdog", Status.FAIL, str(e))

    def test_discovery_optimizer(self) -> TestResult:
        """Test Discovery Optimizer"""
        try:
            resp = requests.get(f"{self.base_url}/api/v1/discovery/status", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    return TestResult("Discovery Optimizer", Status.PASS, "Optimizer ready")
                return TestResult("Discovery Optimizer", Status.WARN, "Not initialized")
            return TestResult("Discovery Optimizer", Status.FAIL, f"Status: {resp.status_code}")
        except Exception as e:
            return TestResult("Discovery Optimizer", Status.FAIL, str(e))

    def test_epss_integration(self) -> TestResult:
        """Test EPSS integration"""
        try:
            resp = requests.get(f"{self.base_url}/api/v1/epss/health", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    return TestResult("EPSS Integration", Status.PASS, "EPSS client ready")
                return TestResult("EPSS Integration", Status.WARN, "EPSS not initialized")
            return TestResult("EPSS Integration", Status.FAIL, f"Status: {resp.status_code}")
        except Exception as e:
            return TestResult("EPSS Integration", Status.FAIL, str(e))

    def run_all_tests(self):
        """Run all verification tests"""
        print("=" * 70)
        print("Kaison K1 Platform v7.6 - Verification Report")
        print("=" * 70)
        print()

        tests = [
            self.test_healthz,
            self.test_orchestrator,
            self.test_watchdog,
            self.test_discovery_optimizer,
            self.test_epss_integration,
            self.test_intelligence_feeds,
            self.test_intelligence_stats,
            self.test_notifications_providers,
            self.test_ollama_status,
            self.test_ollama_models,
            self.test_graph_stats,
        ]

        for test in tests:
            result = test()
            self.results.append(result)
            print(result)

        print()
        print("=" * 70)
        self.print_summary()
        print("=" * 70)

    def print_summary(self):
        """Print test summary"""
        passed = sum(1 for r in self.results if r.status == Status.PASS)
        failed = sum(1 for r in self.results if r.status == Status.FAIL)
        skipped = sum(1 for r in self.results if r.status == Status.SKIP)
        warnings = sum(1 for r in self.results if r.status == Status.WARN)
        total = len(self.results)

        print(f"Total Tests: {total}")
        print(f"Passed:      {passed} {Status.PASS.value}")
        print(f"Failed:      {failed} {Status.FAIL.value}")
        print(f"Warnings:    {warnings} {Status.WARN.value}")
        print(f"Skipped:     {skipped} {Status.SKIP.value}")
        print()

        if failed > 0:
            print("⚠️  Some tests failed. Check backend logs for details.")
            print()
            print("Failed tests:")
            for r in self.results:
                if r.status == Status.FAIL:
                    print(f"  - {r.name}: {r.message}")
        elif warnings > 0:
            print("⚠️  All critical tests passed, but some features are not configured.")
            print()
            print("Warnings:")
            for r in self.results:
                if r.status == Status.WARN:
                    print(f"  - {r.name}: {r.message}")
        else:
            print("✅ All tests passed! Platform is fully operational.")

        return failed == 0


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Verify Kaison K1 Platform v7.6")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)"
    )

    args = parser.parse_args()

    verifier = V76Verifier(base_url=args.url)
    verifier.run_all_tests()

    # Exit with error code if any tests failed
    failed = sum(1 for r in verifier.results if r.status == Status.FAIL)
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
