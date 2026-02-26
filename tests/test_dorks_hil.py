
def test_plan_mode_safe_and_persists_run(client):
    r = client.post("/dorks/run", json={"target": "example.com", "mode": "plan", "chain": "backup_index_chain"})
    assert r.status_code == 200
    b = r.json()
    assert b.get("mode") == "plan"
    assert "executed" in b and isinstance(b["executed"], list)
    assert "run_id" in b and "run_record" in b


def test_execute_blocks_without_hil(client):
    r = client.post("/dorks/run", json={"target": "example.com", "mode": "execute", "chain": "backup_index_chain"})
    assert r.status_code == 409
    assert r.json().get("reason") == "hil_approval_required"


def test_execute_blocks_when_policy_off_even_with_hil(client):
    r = client.post("/dorks/run", json={"target": "example.com", "mode": "execute", "chain": "backup_index_chain", "hil_approved": True})
    assert r.status_code == 409
    assert r.json().get("reason") == "policy_external_queries_disabled"
