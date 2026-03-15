# Kaison AI - Backup and Data Retention Policy

## 1. Overview
This document defines the data retention policy and backup procedures for the KAISON AI (K1) platform, ensuring compliance with security standards and operational continuity.

## 2. Data Retention Policy
The Kaison AI platform enforces a minimum retention period for critical security and operational data.

| Data Category | Minimum Retention | Storage Location |
|---|---|---|
| Vulnerability Findings | 90 Days | PostgreSQL (`findings` table) |
| Scan Audit Logs | 90 Days | PostgreSQL (`audit_events` table) & `authorization_ledger.jsonl` |
| Orchestration Records | 30 Days | PostgreSQL (`campaign_runs`, `phase_jobs`) |
| Artifact Evidence | 90 Days | `artifacts/` volume |

### 2.1 Automated Cleanup
The platform maintains data integrity for the specified period. Older data may be archived or purged automatically to maintain system performance, provided it has been backed up.

## 3. Backup Procedures
Database backups are performed regularly to prevent data loss.

### 3.1 PostgreSQL Backups
For production environments, a `pg_dump` cron job is required.
- **Frequency:** Daily (at minimum)
- **Tool:** `scripts/db-backup.sh`
- **Destination:** `/app/artifacts/backups` (mounted to persistent storage)

### 3.2 Backup Execution
The backup script generates a compressed SQL dump:
```bash
./scripts/db-backup.sh
```

## 4. Restore Procedure
To restore the database from a backup file:

1. **Stop dependent services:**
   ```bash
   docker-compose stop backend worker
   ```

2. **Clear existing database (WARNING: Destructive):**
   ```bash
   docker-compose exec postgres dropdb -U k1 k1
   docker-compose exec postgres createdb -U k1 k1
   ```

3. **Restore from backup:**
   ```bash
   gunzip -c artifacts/backups/k1_backup_TIMESTAMP.sql.gz | docker-compose exec -T postgres psql -U k1 k1
   ```

4. **Restart services:**
   ```bash
   docker-compose start backend worker
   ```

## 5. Persistence Configuration
The platform uses Docker named volumes for persistent storage:
- `postgres_data`: Persistent storage for the PostgreSQL database.
- `redis_data`: Persistent storage for Redis state.
- `./artifacts`: Host-mounted directory for logs, backups, and evidence.
