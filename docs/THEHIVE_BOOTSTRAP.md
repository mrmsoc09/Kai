TheHive First-Run Bootstrap (Dev)

1) Access UI at http://localhost:9000 and create the initial admin user if prompted.
2) Log in as admin → Administration → Users → Create an API key for the backend service.
3) Capture:
   - THEHIVE_URL=http://thehive:9000 (inside compose) or http://localhost:9000 (host)
   - THEHIVE_API_KEY=<generated>
4) Update backend environment:
   - In docker-compose.dev.yml under backend, set THEHIVE_API_KEY to the generated value (or supply via .env).
5) Optional: Create a default case template and organization if required by your workflow.
