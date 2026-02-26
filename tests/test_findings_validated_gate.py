

def test_validated_requires_recording(client):
    # create a safe plan run (no external)
    r = client.post('/dorks/run', json={"target":"example.com","mode":"plan","chain":"backup_index_chain"})
    assert r.status_code == 200
    run_id = r.json()['run_id']

    # attempt to set VALIDATED without recording
    r2 = client.post('/findings/set_status', json={"run_id": run_id, "status": "VALIDATED"})
    assert r2.status_code == 409
    assert r2.json().get('reason') == 'recording_required'

    # now set with recording
    r3 = client.post('/findings/set_status', json={"run_id": run_id, "status": "VALIDATED", "recording_path": "/evidence/demo_recording.mp4"})
    assert r3.status_code == 200
    body = r3.json()
    assert body['ok'] is True
    assert body['artifacts'].get('recording_path') == "/evidence/demo_recording.mp4"
