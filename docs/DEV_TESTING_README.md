# Developer Testing (No Mocks)

1) Bring up infra stack:
   make up

2) Apply DB schema automatically (mounted). Verify:
   make psql
   k1=> \dt

3) Configure HiL API env:
   cp k1/apps/backend/hil_api/.env.example k1/apps/backend/hil_api/.env
   # Ensure DATABASE_URL points to postgres in compose (host=localhost) and THEHIVE_* set.

4) Install deps and run API:
   cd k1/apps/backend/hil_api
   pip install -r requirements.txt
   ./run.sh

5) Test flow (use X-API-Key header):
   # Create finding
   curl -s -X POST http://localhost:8080/findings/ -H 'X-API-Key: user_secret_key_default' -H 'Content-Type: application/json' \
     -d '{"program":"h1/example","asset":"example.com","title":"IDOR in order endpoint","description":"User can access other orders.","severity":"HIGH"}'

   # Add evidence (sha256 hex of artifact)
   curl -s -X POST http://localhost:8080/findings/<id>/evidence -H 'X-API-Key: user_secret_key_default' -H 'Content-Type: application/json' \
     -d '{"kind":"http_trace","uri":"file:///artifacts/trace1.json","sha256_hex":"<hex>"}'

   # Request HiL
   curl -s -X POST http://localhost:8080/hil/findings/<id>/request -H 'X-API-Key: user_secret_key_default' -H 'Content-Type: application/json' -d '{"notes":"ready for review"}'

   # Approve (admin)
   curl -s -X POST http://localhost:8080/hil/findings/<id>/approve -H 'X-API-Key: admin_secret_key_default' -H 'Content-Type: application/json' \
     -d '{"checklist": {"repro_steps":true,"http_traces_or_logs":true,"poc_or_screencap":true,"scope_confirmation":true,"impact_rationale":true}}'

   # Submit (user) — requires TheHive reachable
   curl -s -X POST http://localhost:8080/hil/findings/<id>/submit -H 'X-API-Key: user_secret_key_default' -H 'Content-Type: application/json' \
     -d '{"report_content_hash_hex":"<hex>"}'

