# Phase 6: Report Generation API Reference

Complete REST API documentation for Phase 6 report generation system.

---

## Base URL

```
/reports
```

All endpoints require authentication with `ROLE_OPERATOR` or `ROLE_ANALYST` role.

---

## Endpoints

### 1. Generate Multi-Format Report

Generate report in all supported formats simultaneously.

```
POST /reports/generate-all
```

**Authentication:** Required (`ROLE_OPERATOR` or `ROLE_ANALYST`)

**Request Body:**

```json
{
  "stakeholder": "google_vrp",
  "finding": {
    "title": "SQL Injection in Login Form",
    "severity": "high",
    "cvss": "8.2",
    "cwe": "CWE-89",
    "summary": "Detailed summary of vulnerability",
    "impact": "Detailed impact description",
    "scope": "Affected scope",
    "attack_scenario": "How to reproduce",
    "endpoints": ["/api/login", "/auth"]
  },
  "evidence": {
    "repro": "Step-by-step reproduction",
    "artifacts": {"screenshot": "path/to/image.png"},
    "code_example": "SELECT * FROM users WHERE username='...'",
    "error_logs": "Application error output"
  },
  "mitigation": {
    "plan": "Mitigation steps",
    "timeline": "Timeline for fix",
    "steps": ["Step 1", "Step 2", "Step 3"]
  },
  "include_validation": true,
  "async_generation": false
}
```

**Response (200 OK):**

```json
{
  "ok": true,
  "result": {
    "report_id": "REPORT_GOOGLE_VRP_20260202_a1b2c3d4",
    "stakeholder": "google_vrp",
    "formats": {
      "markdown": {
        "size_bytes": 1024,
        "generated_at": "2026-02-02T12:00:00"
      },
      "html": {
        "size_bytes": 2048,
        "generated_at": "2026-02-02T12:00:00"
      },
      "pdf": {
        "size_bytes": 8192,
        "generated_at": "2026-02-02T12:00:00"
      },
      "json": {
        "size_bytes": 3096,
        "generated_at": "2026-02-02T12:00:00"
      }
    },
    "total_size_bytes": 14360,
    "validation": {
      "ok": true,
      "compliance_score": 92.5,
      "errors": [],
      "warnings": [],
      "detected_multipliers": [
        "deterministic_repro",
        "scope_explicitly_cited",
        "CWE_referenced",
        "CVSS_provided"
      ],
      "recommendations": []
    }
  }
}
```

**Error Responses:**

- `400 Bad Request` - Missing required fields
- `422 Unprocessable Entity` - Invalid field values
- `500 Internal Server Error` - Generation failed

**Example cURL:**

```bash
curl -X POST http://localhost:8000/reports/generate-all \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "stakeholder": "google_vrp",
    "finding": {...},
    "evidence": {...},
    "mitigation": {...}
  }'
```

---

### 2. Embed Evidence

Embed evidence artifacts (code snippets, logs, captures) in reports.

```
POST /reports/embed-evidence
```

**Authentication:** Required

**Request Body:**

```json
{
  "finding_id": "FINDING_001",
  "evidence_type": "code_snippet",
  "content": "SELECT * FROM users WHERE id = ?;",
  "description": "Parameterized query fix",
  "metadata": {
    "language": "sql"
  }
}
```

**Evidence Types:**

- `code_snippet` - Source code or script
- `log_output` - Application or system logs
- `network_capture` - PCAP file (base64 encoded)
- `screenshot` - Image file (base64 encoded)

**Metadata by Type:**

**code_snippet:**
```json
{
  "language": "python|sql|javascript|...",
  "line_numbers": true,
  "syntax_highlight": true
}
```

**log_output:**
```json
{
  "max_lines": 100,
  "truncate": true,
  "format": "plain|json|structured"
}
```

**network_capture:**
```json
{
  "format": "pcap|pcapng",
  "compression": true
}
```

**screenshot:**
```json
{
  "compression": true,
  "quality": 85,
  "watermark": "evidence"
}
```

**Response (200 OK):**

```json
{
  "ok": true,
  "embedding": {
    "evidence_id": "EV_FINDING_001_CODE_SNIPPET_a1b2c3d4",
    "finding_id": "FINDING_001",
    "type": "code_snippet",
    "language": "sql",
    "markdown_block": "```sql\nSELECT * FROM users WHERE id = ?;\n```",
    "metadata": {
      "evidence_id": "EV_FINDING_001_CODE_SNIPPET_a1b2c3d4",
      "evidence_type": "code_snippet",
      "original_filename": "poc.sql",
      "content_hash": "sha256_hash...",
      "compressed_size_bytes": 48,
      "original_size_bytes": 48,
      "compression_ratio": 0.0,
      "watermark_text": "Parameterized query fix",
      "chain_hash": "chain_hash...",
      "embedded_at": "2026-02-02T12:00:00",
      "embedded_by": "evidence_embedder"
    },
    "stats": {
      "lines_of_code": 1,
      "characters": 48,
      "language": "sql"
    }
  },
  "embedded_at": "2026-02-02T12:00:00"
}
```

**Error Responses:**

- `400 Bad Request` - Missing or invalid evidence type
- `422 Unprocessable Entity` - Invalid content
- `500 Internal Server Error` - Embedding failed

---

### 3. Get Cache Statistics

Retrieve statistics about cached reports.

```
GET /reports/cache/stats
```

**Authentication:** Required

**Response (200 OK):**

```json
{
  "ok": true,
  "statistics": {
    "total_cached": 42,
    "active_reports": 38,
    "cache_ttl_minutes": 60,
    "timestamp": "2026-02-02T12:00:00"
  }
}
```

**Example cURL:**

```bash
curl -X GET http://localhost:8000/reports/cache/stats \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

### 4. Retrieve Cached Report

Get a previously generated report from cache.

```
GET /reports/cache/{report_id}
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| report_id | string | Yes | Report ID from generation response |

**Authentication:** Required

**Response (200 OK):**

```json
{
  "ok": true,
  "report_id": "REPORT_GOOGLE_VRP_20260202_a1b2c3d4",
  "report": {
    "ok": true,
    "result": {
      "report_id": "REPORT_GOOGLE_VRP_20260202_a1b2c3d4",
      "stakeholder": "google_vrp",
      "formats": {...},
      "validation": {...}
    }
  },
  "retrieved_at": "2026-02-02T12:00:00"
}
```

**Error Responses:**

- `404 Not Found` - Report not found or expired
- `500 Internal Server Error` - Retrieval failed

**Example cURL:**

```bash
curl -X GET http://localhost:8000/reports/cache/REPORT_GOOGLE_VRP_20260202_a1b2c3d4 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

### 5. Delete Cached Report

Remove a report from cache.

```
DELETE /reports/cache/{report_id}
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| report_id | string | Yes | Report ID to delete |

**Authentication:** Required (`ROLE_OPERATOR` only)

**Response (200 OK):**

```json
{
  "ok": true,
  "report_id": "REPORT_GOOGLE_VRP_20260202_a1b2c3d4",
  "deleted_at": "2026-02-02T12:00:00"
}
```

**Error Responses:**

- `404 Not Found` - Report not in cache
- `403 Forbidden` - Insufficient permissions
- `500 Internal Server Error` - Deletion failed

**Example cURL:**

```bash
curl -X DELETE http://localhost:8000/reports/cache/REPORT_GOOGLE_VRP_20260202_a1b2c3d4 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Stakeholder IDs

Supported stakeholder/format IDs:

| ID | Name | Focus |
|---|---|---|
| `google_vrp` | Google VRP | Timeline & scope |
| `hackerone` | HackerOne | Technical details |
| `bugcrowd` | Bugcrowd | Business impact |
| `intigriti` | Intigriti | Data exposure |
| `msrc` | MSRC | Product versions |

---

## Validation Result Structure

```json
{
  "ok": boolean,
  "stakeholder": "string",
  "compliance_score": 0-100,
  "content_metrics": {
    "total_lines": integer,
    "total_words": integer,
    "average_line_length": integer,
    "code_blocks": integer,
    "images": integer,
    "links": integer,
    "bold_sections": integer
  },
  "issues": [
    {
      "section": "string",
      "level": "error|warning|info",
      "message": "string"
    }
  ],
  "errors": [...],
  "warnings": [...],
  "missing_sections": [...],
  "detected_multipliers": [
    "deterministic_repro",
    "scope_explicitly_cited",
    "minimal_data_exposure",
    "no_service_degradation",
    "CWE_referenced",
    "CVSS_provided",
    "PoC_code_included",
    "attack_narrative_clarity",
    "business_impact_clear",
    "version_info_clear",
    "platform_specific"
  ],
  "recommendations": ["string"]
}
```

---

## Request/Response Examples

### Example 1: Generate SQL Injection Report for Google VRP

**Request:**

```bash
curl -X POST http://localhost:8000/reports/generate-all \
  -H "Authorization: Bearer token" \
  -H "Content-Type: application/json" \
  -d '{
    "stakeholder": "google_vrp",
    "finding": {
      "title": "SQL Injection in User Search",
      "severity": "critical",
      "cvss": "9.1",
      "cwe": "CWE-89",
      "summary": "The user search endpoint does not properly sanitize input, allowing SQL injection attacks that can lead to unauthorized database access and data exfiltration.",
      "impact": "Complete database compromise, unauthorized access to all user data, potential system takeover",
      "scope": "User search functionality at /api/users/search endpoint",
      "attack_scenario": "Attacker submits SQL payload in search query parameter",
      "endpoints": ["/api/users/search"]
    },
    "evidence": {
      "repro": "1. Navigate to /api/users/search?q=test\n2. Modify query to /api/users/search?q=1' OR '1'='1\n3. Observe SQL error revealing database structure\n4. Extract user data",
      "artifacts": {"error_output": "database_error_screenshot.png"},
      "code_example": "const users = db.query(`SELECT * FROM users WHERE email LIKE '${req.query.q}%'`);"
    },
    "mitigation": {
      "plan": "Use parameterized queries with prepared statements",
      "timeline": "Can be fixed in patch 1.2.1 (3 days)",
      "steps": ["Refactor all database queries to use parameterized queries", "Add input validation", "Deploy Web Application Firewall rules"]
    },
    "include_validation": true
  }'
```

**Response:**

```json
{
  "ok": true,
  "result": {
    "report_id": "REPORT_GOOGLE_VRP_20260202_a1b2c3d4",
    "stakeholder": "google_vrp",
    "formats": {
      "markdown": {"size_bytes": 2048, "generated_at": "..."},
      "html": {"size_bytes": 4096, "generated_at": "..."},
      "pdf": {"size_bytes": 16384, "generated_at": "..."},
      "json": {"size_bytes": 3072, "generated_at": "..."}
    },
    "validation": {
      "ok": true,
      "compliance_score": 95.2,
      "detected_multipliers": [
        "deterministic_repro",
        "scope_explicitly_cited",
        "CWE_referenced",
        "CVSS_provided",
        "PoC_code_included"
      ]
    }
  }
}
```

### Example 2: Embed Proof-of-Concept Code

**Request:**

```bash
curl -X POST http://localhost:8000/reports/embed-evidence \
  -H "Authorization: Bearer token" \
  -H "Content-Type: application/json" \
  -d '{
    "finding_id": "SQL_INJECTION_USER_SEARCH",
    "evidence_type": "code_snippet",
    "content": "curl \"http://localhost:3000/api/users/search?q=1%27%20OR%20%271%27=%271\"",
    "description": "Proof of concept - SQL injection attack",
    "metadata": {
      "language": "bash"
    }
  }'
```

**Response:**

```json
{
  "ok": true,
  "embedding": {
    "evidence_id": "EV_SQL_INJECTION_USER_SEARCH_CODE_SNIPPET_a1b2c3d4",
    "type": "code_snippet",
    "language": "bash",
    "markdown_block": "```bash\ncurl \"http://localhost:3000/api/users/search?q=1%27%20OR%20%271%27=%271\"\n```",
    "stats": {
      "lines_of_code": 1,
      "characters": 76,
      "language": "bash"
    }
  }
}
```

---

## Error Handling

All error responses follow this format:

```json
{
  "detail": "error message describing what went wrong"
}
```

**Common HTTP Status Codes:**

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Request completed successfully |
| 400 | Bad Request | Check request format and required fields |
| 401 | Unauthorized | Missing or invalid authentication token |
| 403 | Forbidden | Insufficient permissions for operation |
| 404 | Not Found | Resource does not exist or expired |
| 422 | Unprocessable | Request format valid but content invalid |
| 500 | Server Error | Internal server error; check logs |

---

## Rate Limiting

Currently no rate limiting implemented. For production:

**Recommended Limits:**
- Generate-all: 10 requests/minute per user
- Embed-evidence: 100 requests/minute per user
- Cache operations: 100 requests/minute per user

---

## Authentication

Include `Authorization` header with Bearer token:

```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" http://localhost:8000/reports/...
```

Required roles: `ROLE_OPERATOR` or `ROLE_ANALYST`

---

## Caching Behavior

**Cache Key:** `report_id` (e.g., `REPORT_GOOGLE_VRP_20260202_a1b2c3d4`)

**TTL:** 60 minutes (configurable via `CACHE_TTL_MINUTES`)

**Automatic Cleanup:** Expired reports removed when accessed

**Manual Cleanup:** Use DELETE endpoint to remove reports

---

## Response Size Limits

| Format | Typical Size | Max Size |
|--------|--------------|----------|
| Markdown | 2-10 KB | 100 KB |
| HTML | 5-20 KB | 200 KB |
| PDF | 50-100 KB | 500 KB |
| JSON | 5-20 KB | 100 KB |

---

## Pagination & Filtering

Currently not implemented. Future versions may include:

- `GET /reports/cache/list?limit=50&offset=0`
- `GET /reports/cache/list?stakeholder=google_vrp`
- `GET /reports/cache/list?date_from=2026-02-01`

---

## Webhooks (Future)

Planned webhook support for:

- Report generation complete
- Validation results available
- Cache expiration
- Error events

---

## Version History

### v1.0 (Feb 2, 2026)
- Initial release
- Multi-format export
- Evidence embedding
- Cache management
- Validation integration

---

## Support

For API issues:

1. Check response error messages
2. Verify request format matches examples
3. Confirm authentication token validity
4. Review server logs: `./logs/reports.log`
5. Contact development team

---

**API Reference v1.0**
Last Updated: February 2, 2026
