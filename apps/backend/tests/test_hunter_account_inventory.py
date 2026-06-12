from __future__ import annotations

from apps.backend.src.core.hunter_account_inventory import inventory_from_csv_rows


def test_inventory_parses_hunter_accounts_and_keys():
    rows = [
        {
            "type": "login",
            "name": "HackerOne",
            "url": "https://hackerone.com/users/sign_in",
            "email": "researcher@example.com",
            "username": "researcher01",
            "password": "secret-password",
            "note": "backup codes stored separately",
            "totp": "123456",
            "createTime": "",
            "modifyTime": "",
            "vault": "",
        }
    ]

    records, summary = inventory_from_csv_rows(rows, source_path="/tmp/proton.csv")
    assert summary["record_count"] == 1
    assert summary["counts"]["hunter_account"] == 1
    assert records[0].credential_kind == "hunter_account"
    assert records[0].platform_hint == "hackerone"
    assert records[0].has_password is True
    assert records[0].has_totp is True
