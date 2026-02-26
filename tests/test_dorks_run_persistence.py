import os


def test_plan_mode_persists_run_record(client, tmp_path=None):
    r = client.post("/dorks/run", json={"target":"example.com","mode":"plan","chain":"backup_index_chain"})
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "plan"
    assert body.get("run_id")
    assert body.get("run_record")
    assert os.path.exists(body["run_record"]) is True
