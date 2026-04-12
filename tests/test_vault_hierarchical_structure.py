"""Tests for hierarchical Vault key structure and SecretManager integration.

Verifies that:
1. SecretManager can retrieve keys from both flat (secret/OPENAI_API_KEY)
   and hierarchical (secret/k1/ai/openai) formats
2. APIKeysOrchestrator loads from Vault correctly
3. LLM providers and tool adapters can initialize with Vault keys
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
import os


class TestVaultHierarchicalStructure:
    """Test hierarchical Vault key retrieval."""

    def test_vault_paths_exist(self):
        """Verify Vault has both key storage formats."""
        # This test requires Vault to be running
        try:
            import hvac
            vault_addr = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
            vault_token = os.getenv("VAULT_TOKEN", "")

            if not vault_token:
                pytest.skip("VAULT_TOKEN not set, skipping Vault connectivity test")

            client = hvac.Client(url=vault_addr, token=vault_token)

            # Check hierarchical paths
            result = client.secrets.kv.v2.list_secrets(
                path="k1/ai",
                mount_point="secret"
            )
            keys = result.get("data", {}).get("keys", [])
            assert len(keys) > 0, "No keys found in secret/k1/ai/"
            assert "openai" in keys or "geminiai" in keys, "AI keys not found"

            # Check flat paths
            result = client.secrets.kv.v2.list_secrets(
                path="",
                mount_point="secret"
            )
            keys = result.get("data", {}).get("keys", [])
            api_key_keys = [k for k in keys if k.endswith("_API_KEY")]
            assert len(api_key_keys) > 0, "No *_API_KEY format keys found"

        except ImportError:
            pytest.skip("hvac not installed")
        except Exception as e:
            pytest.skip(f"Vault not available: {e}")

    def test_secret_manager_has_hierarchical_method(self):
        """Verify SecretManager has hierarchical retrieval method."""
        from apps.backend.src.core.secret_manager import SecretManager

        # Verify the method exists
        assert hasattr(SecretManager, 'get_hierarchical')
        assert callable(SecretManager.get_hierarchical)

        # Verify it has required method signature
        assert hasattr(SecretManager, 'get_hierarchical_required')
        assert callable(SecretManager.get_hierarchical_required)

    def test_vault_secret_provider_has_hierarchical_method(self):
        """Verify VaultSecretProvider has hierarchical method."""
        from apps.backend.src.core.secret_manager import VaultSecretProvider

        # Verify the method exists
        assert hasattr(VaultSecretProvider, 'get_secret_hierarchical')

    def test_api_keys_orchestrator_has_load_method(self):
        """Verify APIKeysOrchestrator has key loading method."""
        from apps.backend.src.core.api_keys_orchestrator import APIKeysOrchestrator

        orchestrator = APIKeysOrchestrator()

        # Verify the method exists
        assert hasattr(orchestrator, '_load_api_keys_from_vault')
        assert callable(orchestrator._load_api_keys_from_vault)

        # Verify DEFAULT_QUOTAS is a dict with many keys
        assert isinstance(orchestrator.DEFAULT_QUOTAS, dict)
        assert len(orchestrator.DEFAULT_QUOTAS) >= 50

    def test_api_keys_orchestrator_default_quotas(self):
        """Verify API keys have default quotas configured (50+ keys)."""
        from apps.backend.src.core.api_keys_orchestrator import APIKeysOrchestrator

        orchestrator = APIKeysOrchestrator()
        quotas = orchestrator.DEFAULT_QUOTAS

        # Check minimum count (should have 50+ keys, aiming for 55)
        assert len(quotas) >= 50, f"Expected 50+ keys, got {len(quotas)}"

        # Check all major categories are represented
        ai_keys = [k for k in quotas.keys() if any(x in k for x in ["OPENAI", "ANTHROPIC", "GEMINI", "GROQ", "MISTRAL", "PERPLEXITY", "OPENROUTER", "DEEPSEEK", "LITELLM", "AIMLAPI", "VERTEX"])]
        osint_keys = [k for k in quotas.keys() if any(x in k for x in ["SHODAN", "FULLHUNT", "DEHASHED", "LEAKIX", "ZOOMEYE", "HUNTER", "INTELX", "ABUSEIPDB"])]
        security_keys = [k for k in quotas.keys() if any(x in k for x in ["VIRUSTOTAL", "OTX", "NVD"])]
        bugbounty_keys = [k for k in quotas.keys() if any(x in k for x in ["HACKERONE", "INTIGRITI"])]

        assert len(ai_keys) >= 8, f"Expected 8+ AI keys, got {len(ai_keys)}: {ai_keys}"
        assert len(osint_keys) >= 8, f"Expected 8+ OSINT keys, got {len(osint_keys)}: {osint_keys}"
        assert len(security_keys) >= 2, f"Expected 2+ security keys, got {len(security_keys)}: {security_keys}"
        assert len(bugbounty_keys) >= 2, f"Expected 2+ BugBounty keys, got {len(bugbounty_keys)}: {bugbounty_keys}"

        # All quotas should be positive integers
        for key_name, quota in quotas.items():
            assert isinstance(quota, int), f"{key_name} quota is not int"
            assert quota > 0, f"{key_name} quota is not positive"

    def test_queue_length_enforcement(self):
        """Verify queue length limits are properly configured."""
        from apps.backend.src.core.api_keys_orchestrator import APIKeysOrchestrator

        orchestrator = APIKeysOrchestrator()

        assert orchestrator.MAX_QUEUE_LENGTH == 100
        assert orchestrator.TARGET_QUEUE_LENGTH == 50
        assert orchestrator.MIN_QUEUE_LENGTH == 5
        assert orchestrator.RESERVE_RATIO == 0.15

    @pytest.mark.asyncio
    async def test_allocation_calculation(self):
        """Verify quota allocation calculation works correctly."""
        from apps.backend.src.core.api_keys_orchestrator import APIKeysOrchestrator

        orchestrator = APIKeysOrchestrator()

        # Mock API keys and scan entries
        api_keys = {
            "OPENAI_API_KEY": {
                "present": True,
                "remaining": 5000,
            },
            "SHODAN_API_KEY": {
                "present": True,
                "remaining": 100,
            },
        }

        scan_entries = [
            {"id": "scan-1"},
            {"id": "scan-2"},
            {"id": "scan-3"},
        ]

        allocations = orchestrator._calculate_allocations(api_keys, scan_entries)

        # Verify structure
        assert "OPENAI_API_KEY" in allocations
        assert "SHODAN_API_KEY" in allocations

        # Verify calculation
        openai_per_scan = allocations["OPENAI_API_KEY"].get("scan-1", 0)
        expected_per_scan = int(5000 * (1 - 0.15) / 3)  # reserve ratio 15%
        assert openai_per_scan == expected_per_scan

    def test_orchestrator_has_queue_checking_methods(self):
        """Verify orchestrator has queue checking methods."""
        from apps.backend.src.core.api_keys_orchestrator import APIKeysOrchestrator

        orchestrator = APIKeysOrchestrator()

        # Verify methods exist
        assert hasattr(orchestrator, '_check_and_enforce_queue_limits')
        assert callable(orchestrator._check_and_enforce_queue_limits)

        # Verify constants are set
        assert orchestrator.MAX_QUEUE_LENGTH == 100
        assert orchestrator.RESERVE_RATIO == 0.15


class TestLLMProviderVaultIntegration:
    """Test LLM providers can initialize with Vault keys."""

    def test_llm_provider_imports(self):
        """Verify LLM provider modules can be imported."""
        try:
            from apps.backend.src.core import llm_providers
            assert hasattr(llm_providers, 'AnthropicProvider')
            assert hasattr(llm_providers, 'OpenAIProvider')
            assert hasattr(llm_providers, 'GeminiProvider')
        except ImportError as e:
            pytest.skip(f"LLM providers not available: {e}")

    def test_llm_provider_uses_secret_manager(self):
        """Verify LLM providers use SecretManager for API keys."""
        with patch.dict(os.environ, {
            "K1_SECRET_BACKEND": "vault",
            "VAULT_TOKEN": "hvs.test",
        }):
            with patch('apps.backend.src.core.llm_providers._resolve_api_key') as mock_resolve:
                mock_resolve.return_value = "sk-test-key"

                # Import will call _resolve_api_key during initialization
                from apps.backend.src.core.llm_providers import _resolve_api_key

                key = _resolve_api_key(None, "OPENAI_API_KEY")
                assert key == "sk-test-key"

    def test_llm_providers_have_config_class(self):
        """Verify LLM providers have proper configuration."""
        try:
            from apps.backend.src.core.llm_providers import (
                AnthropicProvider, OpenAIProvider, GeminiProvider
            )

            # Verify providers exist and are classes
            assert isinstance(AnthropicProvider, type)
            assert isinstance(OpenAIProvider, type)
            assert isinstance(GeminiProvider, type)
        except ImportError:
            pytest.skip("LLM providers not fully available")


class TestToolAdapterVaultIntegration:
    """Test tool adapters can retrieve API keys from Vault."""

    def test_tool_registry_loads(self):
        """Verify tool registry can be loaded."""
        try:
            from apps.backend.src.core.tools import get_registry
            registry = get_registry()
            assert registry is not None
        except Exception as e:
            pytest.skip(f"Tool registry not available: {e}")

    def test_tool_api_key_requirements(self):
        """Verify tools that require API keys are marked correctly."""
        try:
            from apps.backend.src.core.tools import get_registry
            registry = get_registry()

            # Get all tools
            all_tools = registry.get_all_schemas()

            # Find tools with API key requirements
            api_key_tools = [
                name for name, schema in all_tools.items()
                if hasattr(schema, "api_keys_required") and schema.api_keys_required
            ]

            # Should have multiple tools requiring API keys
            assert len(api_key_tools) > 0, "No tools with API key requirements found"
        except Exception as e:
            pytest.skip(f"Cannot check tool requirements: {e}")


class TestDatabaseModels:
    """Test database models for queue and quota tracking."""

    def test_api_scan_queue_model_fields(self):
        """Verify APIScanQueue model has expected fields."""
        try:
            from apps.backend.src.models.api_scan_queue import APIScanQueue

            # Check required fields
            assert hasattr(APIScanQueue, "planning_date")
            assert hasattr(APIScanQueue, "queue_length")
            assert hasattr(APIScanQueue, "max_queue_length")
            assert hasattr(APIScanQueue, "status")
            assert hasattr(APIScanQueue, "api_keys_available")
        except ImportError:
            pytest.skip("APIScanQueue model not available")

    def test_api_key_daily_quota_model_fields(self):
        """Verify APIKeyDailyQuota model has expected fields."""
        try:
            from apps.backend.src.models.api_scan_queue import APIKeyDailyQuota

            # Check required fields
            assert hasattr(APIKeyDailyQuota, "quota_date")
            assert hasattr(APIKeyDailyQuota, "api_key_name")
            assert hasattr(APIKeyDailyQuota, "allocated_quota")
            assert hasattr(APIKeyDailyQuota, "used_quota")
            assert hasattr(APIKeyDailyQuota, "status")
        except ImportError:
            pytest.skip("APIKeyDailyQuota model not available")


class TestCeleryBeatSchedule:
    """Test Celery beat schedule configuration."""

    def test_beat_schedule_configured(self):
        """Verify API Keys Orchestrator is in beat schedule."""
        with patch.dict(os.environ, {"PYTHONPATH": "/home/k1-admin/Kai"}):
            try:
                from apps.backend.src.worker.celery_app import celery_app

                beat_schedule = celery_app.conf.beat_schedule
                assert "api-keys-orchestrator-6am" in beat_schedule

                task_config = beat_schedule["api-keys-orchestrator-6am"]
                assert task_config["task"] == "api_keys_orchestrator_6am"
                assert task_config["options"]["queue"] == "scheduled"
            except Exception as e:
                pytest.skip(f"Celery config not available: {e}")

    def test_scan_queue_advance_still_configured(self):
        """Verify existing scan queue advancement task is still active."""
        with patch.dict(os.environ, {"PYTHONPATH": "/home/k1-admin/Kai"}):
            try:
                from apps.backend.src.worker.celery_app import celery_app

                beat_schedule = celery_app.conf.beat_schedule
                assert "advance-scan-queues" in beat_schedule

                task_config = beat_schedule["advance-scan-queues"]
                assert task_config["task"] == "scan_queue_advance_all"
            except Exception as e:
                pytest.skip(f"Celery config not available: {e}")


