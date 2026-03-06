from __future__ import annotations

from scripts import check_toolpack_adapter_compat, check_unmanaged_secrets, check_non_bypassability


def test_toolpack_adapter_compatibility_gate_passes():
    assert check_toolpack_adapter_compat.main() == 0


def test_unmanaged_secret_read_gate_passes():
    assert check_unmanaged_secrets.main() == 0


def test_non_bypassability_gate_passes():
    assert check_non_bypassability.main() == 0
