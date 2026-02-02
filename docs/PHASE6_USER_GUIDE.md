# Phase 6: Report Generation System - User Guide

## Overview

Phase 6 introduces a comprehensive report generation system that enables automated creation of vulnerability reports in multiple formats optimized for different vulnerability reporting programs (VRPs).

**Key Features:**
- Multi-format export (Markdown, HTML, PDF, JSON)
- Jinja2 template rendering with dynamic content
- Professional PDF generation with styling
- Content quality validation with compliance scoring
- Evidence embedding with integrity verification
- Reward multiplier detection
- Report caching for performance

---

## Getting Started

### Installation

Install Phase 6 dependencies:

```bash
pip install -r requirements.txt --upgrade
```

New dependencies added:
- `weasyprint>=60.0` - PDF generation
- `Markdown>=3.5` - Markdown processing
- `bleach>=6.0` - HTML sanitization
- `Pillow>=10.0` - Image processing

### Quick Start

Generate a report in all formats:

```python
from core.format_exporter import create_exporter

# Create exporter for Google VRP format
exporter = create_exporter("google_vrp")

# Prepare finding, evidence, and mitigation data
finding = {
    "title": "SQL Injection in Login Form",
    "severity": "high",
    "cvss": "8.2",
    "cwe": "CWE-89",
    "summary": "...",
    "impact": "...",
}

evidence = {
    "repro": "1. Navigate to login\n2. Enter SQL payload\n...",
    "artifacts": {"screenshot": "login_bypass.png"},
}

mitigation = {
    "plan": "Use parameterized queries",
    "timeline": "Fix in v2.1 (2 days)",
}

# Export to all formats
exports = exporter.export_all(finding, evidence, mitigation)

# Access individual formats
pdf_bytes = exports['pdf']
markdown_content = exports['markdown']
html_content = exports['html']
json_data = exports['json']
```

---

## Core Components

### 1. Report Formats (Jinja2 Templates)

Five VRP-specific formats with Jinja2 templates:

#### Google VRP
- **Focus:** Security timeline and scope limitation
- **Key Sections:** Executive summary, attack scenario, affected scope, reproduction steps
- **Template Variables:** 40+ including attack_scenario, timeline, endpoints

#### HackerOne
- **Focus:** Technical details and financial impact
- **Key Sections:** Weakness type, severity, PoC code, remediation steps
- **Template Variables:** 40+ including weakness_type, asset_identifier, financial_impact

#### Bugcrowd
- **Focus:** Business impact and effort estimation
- **Key Sections:** Vulnerability type, business impact, evidence artifacts
- **Template Variables:** 35+ including business_impact, effort_estimate

#### Intigriti
- **Focus:** Data exposure and access levels
- **Key Sections:** Data exposure tracking, access requirements, priority field
- **Template Variables:** 40+ including data_exposure_type, access_level

#### MSRC
- **Focus:** Product versions and affected components
- **Key Sections:** Product tracking, affected versions, attack complexity
- **Template Variables:** 40+ including affected_versions, attack_complexity

### 2. PDF Generation

Generate professional PDF reports from markdown:

```python
from core.pdf_generator import generate_pdf_from_markdown

# Generate PDF
pdf_bytes = generate_pdf_from_markdown(
    markdown_content="# Report\n## Summary\n...",
    stakeholder="hackerone"
)

# Save to file
output_path.write_bytes(pdf_bytes)
```

**PDF Features:**
- A4 page size with professional margins
- Color-coded severity levels
- Code syntax highlighting
- Table support with alternating row colors
- Image embedding
- Professional typography

### 3. Multi-Format Export

Export reports in multiple formats simultaneously:

```python
from core.format_exporter import create_exporter

exporter = create_exporter("google_vrp")

# Export all formats at once
all_exports = exporter.export_all(
    finding,
    evidence,
    mitigation,
    output_dir="./reports/"  # Optional: save to disk
)

# Export single format
pdf = exporter.export(finding, evidence, mitigation, format_type="pdf")
markdown = exporter.export(finding, evidence, mitigation, format_type="markdown")
json_data = exporter.export(finding, evidence, mitigation, format_type="json")

# Get statistics
stats = exporter.get_export_stats()
print(f"Total exports: {stats['total_exports']}")
print(f"Average file size: {stats['average_size_kb']}KB")
```

**Supported Formats:**
1. **Markdown** - Human-readable, editable format
2. **HTML** - Web-viewable with embedded styles
3. **PDF** - Print-ready professional document
4. **JSON** - Structured data for integration

### 4. Format Validation

Validate report quality against stakeholder-specific rules:

```python
from core.report_validator import validate_rendered

result = validate_rendered(
    stakeholder="google_vrp",
    content=markdown_report,
    has_recording=True,
    finding_data=finding
)

print(f"Compliance Score: {result['compliance_score']:.1f}%")
print(f"Errors: {result['errors']}")
print(f"Warnings: {result['warnings']}")
print(f"Multipliers Detected: {result['detected_multipliers']}")
print(f"Recommendations: {result['recommendations']}")
```

**Validation Checks:**
- Required sections present
- Minimum word counts per section
- Content structure and formatting
- Metadata presence (severity, CWE, CVSS)
- Evidence quality indicators

### 5. Evidence Embedding

Embed and track evidence artifacts with integrity verification:

```python
from core.evidence_embedder import create_embedder

embedder = create_embedder(merkle_chain_enabled=True)

# Embed code snippet
code_result = embedder.embed_code_snippet(
    code_content="SELECT * FROM users WHERE id = ?;",
    language="sql",
    finding_id="FINDING_001",
    description="Fixed SQL query using parameterization"
)

# Embed log output
log_result = embedder.embed_log_output(
    log_content="Error: SQL injection detected\nStack trace...",
    finding_id="FINDING_001",
    description="Application error logs",
    truncate_lines=50  # Limit lines
)

# Verify integrity
verification = embedder.verify_evidence_integrity(code_result["evidence_id"])
print(f"Evidence valid: {verification['valid']}")

# Get manifest of all embedded evidence
manifest = embedder.get_evidence_manifest("FINDING_001")
print(f"Total evidence items: {manifest['total_evidence_items']}")
```

---

## REST API Endpoints

### Generate Multi-Format Report

```
POST /reports/generate-all
```

**Request:**
```json
{
    "stakeholder": "google_vrp",
    "finding": { /* finding data */ },
    "evidence": { /* evidence data */ },
    "mitigation": { /* mitigation data */ },
    "include_validation": true,
    "async_generation": false
}
```

**Response:**
```json
{
    "ok": true,
    "report_id": "REPORT_GOOGLE_VRP_20260202_a1b2c3d4",
    "stakeholder": "google_vrp",
    "formats": {
        "markdown": { "size_bytes": 1024, "generated_at": "..." },
        "html": { "size_bytes": 2048, "generated_at": "..." },
        "pdf": { "size_bytes": 8192, "generated_at": "..." },
        "json": { "size_bytes": 3096, "generated_at": "..." }
    },
    "validation": { /* validation result */ }
}
```

### Embed Evidence

```
POST /reports/embed-evidence
```

**Request:**
```json
{
    "finding_id": "FINDING_001",
    "evidence_type": "code_snippet",
    "content": "SELECT * FROM users WHERE id = ?;",
    "description": "Parameterized query fix",
    "metadata": { "language": "sql" }
}
```

**Response:**
```json
{
    "ok": true,
    "embedding": {
        "evidence_id": "EV_FINDING_001_CODE_SNIPPET_a1b2c3d4",
        "type": "code_snippet",
        "language": "sql",
        "markdown_block": "```sql\nSELECT * FROM users WHERE id = ?;\n```"
    }
}
```

### Get Cache Statistics

```
GET /reports/cache/stats
```

**Response:**
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

### Retrieve Cached Report

```
GET /reports/cache/{report_id}
```

### Delete Cached Report

```
DELETE /reports/cache/{report_id}
```

---

## Validation Requirements by Stakeholder

### Google VRP
- **Summary:** Minimum 50 words
- **Impact:** Minimum 75 words
- **Repro Steps:** Minimum 3 numbered steps
- **Multipliers:** Format compliance, deterministic reproducibility, scope clarity
- **Recording:** Required

### HackerOne
- **Summary:** Minimum 50 words
- **Impact:** Minimum 75 words
- **Repro Steps:** Minimum 2 steps
- **Multipliers:** CWE reference, CVSS score, PoC code
- **Recording:** Recommended

### Bugcrowd
- **Summary:** Minimum 40 words
- **Impact:** Minimum 60 words
- **Repro Steps:** Minimum 2 steps
- **Multipliers:** Attack narrative clarity, business impact
- **Recording:** Recommended

### Intigriti
- **Summary:** Minimum 50 words
- **Impact:** Minimum 75 words
- **Repro Steps:** Minimum 3 steps
- **Multipliers:** CWE reference, reproducibility proof
- **Recording:** Recommended

### MSRC
- **Summary:** Minimum 50 words
- **Impact:** Minimum 75 words
- **Repro Steps:** Minimum 3 steps
- **Multipliers:** Version clarity, platform specificity
- **Recording:** Required

---

## Multiplier Detection

Automatically detect reward multipliers for optimization:

```python
result = validate_rendered(
    stakeholder="hackerone",
    content=markdown_report
)

# Detected multipliers might include:
multipliers = result['detected_multipliers']
# Example: ['deterministic_repro', 'scope_explicitly_cited',
#           'CWE_referenced', 'CVSS_provided', 'PoC_code_included']

print(f"Reward optimization potential: {len(multipliers)} multipliers detected")
```

**Multiplier Indicators:**
1. **Deterministic Repro** - Always reproducible, not intermittent
2. **Scope Explicitly Cited** - Clear boundaries defined
3. **Minimal Data Exposure** - Limited impact radius
4. **CWE Referenced** - Proper classification
5. **CVSS Provided** - Severity quantified
6. **PoC Code Included** - Working proof of concept
7. **Business Impact Clear** - Financial implications stated
8. **Version Info Clear** - Affected versions specified
9. **Platform Specific** - OS/architecture mentioned

---

## Compliance Scoring

Compliance Score ranges:

- **90-100%:** Excellent - Ready for immediate submission
- **80-89%:** Good - Minor improvements suggested
- **70-79%:** Fair - Notable issues to address
- **Below 70%:** Poor - Significant work needed

```python
result = validate_rendered(stakeholder="google_vrp", content=report)

score = result['compliance_score']
if score >= 90:
    print("✅ Excellent compliance")
elif score >= 80:
    print("✅ Good - consider recommendations")
elif score >= 70:
    print("⚠️  Fair - address warnings")
else:
    print("❌ Poor - fix errors first")
```

---

## Performance Characteristics

Typical performance metrics on standard hardware:

| Operation | Time | Throughput |
|-----------|------|-----------|
| PDF Generation | 500-1000ms | ~60 reports/minute |
| HTML Export | 50-100ms | ~600 reports/minute |
| Markdown Export | 10-20ms | ~3000+ reports/minute |
| JSON Export | <10ms | ~5000+ reports/minute |
| Validation | 5-10ms | ~6000+ validations/minute |
| Evidence Embedding | 5-50ms | ~20-200 artifacts/minute |

---

## Common Workflows

### Workflow 1: Generate Report for Single VRP

```python
from core.format_exporter import create_exporter
from core.report_validator import validate_rendered

# Step 1: Create exporter for target VRP
exporter = create_exporter("hackerone")

# Step 2: Generate markdown (base format)
markdown = exporter.export(finding, evidence, mitigation, "markdown")

# Step 3: Validate against stakeholder rules
validation = validate_rendered("hackerone", markdown, has_recording=True, finding_data=finding)

if validation['ok']:
    # Step 4: Generate PDF for submission
    pdf = exporter.export(finding, evidence, mitigation, "pdf")
    # Ready to submit!
```

### Workflow 2: Generate for Multiple VRPs

```python
from core.format_exporter import create_exporter

vrps = ["google_vrp", "hackerone", "bugcrowd"]
reports = {}

for vrp in vrps:
    exporter = create_exporter(vrp)
    reports[vrp] = exporter.export_all(finding, evidence, mitigation)

# Now have all formats for all VRPs ready
for vrp, formats in reports.items():
    pdf = formats['pdf']
    # Submit to each VRP
```

### Workflow 3: Generate with Evidence

```python
from core.format_exporter import create_exporter
from core.evidence_embedder import create_embedder

# Step 1: Generate base report
exporter = create_exporter("google_vrp")
markdown = exporter.export(finding, evidence, mitigation, "markdown")

# Step 2: Create evidence section
embedder = create_embedder(merkle_chain_enabled=True)

# Embed code proof
code_result = embedder.embed_code_snippet(
    code_content=evidence.get("code_example", ""),
    language="python",
    finding_id=finding["title"]
)

# Embed error logs
log_result = embedder.embed_log_output(
    log_content=evidence.get("error_logs", ""),
    finding_id=finding["title"]
)

# Step 3: Add evidence section to report
evidence_section = embedder.create_evidence_section(
    finding_id=finding["title"],
    evidence_ids=[code_result["evidence_id"], log_result["evidence_id"]]
)

final_report = markdown + "\n" + evidence_section

# Step 4: Generate final PDF with evidence
final_pdf = exporter.export(finding, evidence, mitigation, "pdf")
```

---

## Troubleshooting

### Issue: PDF Generation Fails

**Symptoms:** `weasyprint error` or empty PDF

**Solutions:**
1. Ensure weasyprint is installed: `pip install weasyprint --upgrade`
2. Check HTML content is valid
3. Verify system fonts are available
4. Try with simpler markdown content first

### Issue: Validation Always Fails

**Symptoms:** Low compliance score, many warnings

**Solutions:**
1. Ensure all required sections present
2. Increase word counts in summary/impact
3. Add more reproduction steps
4. Include code examples and screenshots
5. Check for typos in section headers

### Issue: Template Rendering Errors

**Symptoms:** `TemplateError` or incomplete content

**Solutions:**
1. Verify all required finding fields present
2. Check for special characters in content
3. Ensure evidence data structure matches template expectations
4. Try rendering with sample data first

### Issue: PDF Size Too Large

**Symptoms:** PDF files >50MB

**Solutions:**
1. Reduce image size/quality
2. Limit number of code blocks
3. Use PDF compression options
4. Split large reports into sections

---

## Best Practices

1. **Always Validate Before Submission**
   ```python
   validation = validate_rendered(...)
   if validation['compliance_score'] < 80:
       print("Fix issues before submitting:")
       for warning in validation['warnings']:
           print(f"  - {warning['message']}")
   ```

2. **Use Multiplier Detection for Optimization**
   ```python
   if len(result['detected_multipliers']) < 5:
       print("Consider adding:")
       print("  - CWE reference")
       print("  - CVSS score")
       print("  - Working PoC")
   ```

3. **Embed Evidence for Credibility**
   - Always include code examples
   - Add screenshots of vulnerable behavior
   - Include error logs and system output

4. **Test with Sample Data First**
   - Use verification script to test all components
   - Validate locally before API submission
   - Check PDF rendering in reader

5. **Monitor Cache Statistics**
   ```python
   # Check cache health
   stats = get_cache_stats()
   active = stats['active_reports']
   print(f"Active reports in cache: {active}")
   ```

---

## API Authentication

All endpoints require `ROLE_OPERATOR` or `ROLE_ANALYST`:

```python
from fastapi import Depends
from core.auth import require_roles, ROLE_OPERATOR

@router.post("/generate-all")
async def endpoint(_=Depends(require_roles(ROLE_OPERATOR))):
    # Endpoint implementation
    pass
```

---

## Next Steps

- **Advanced Features:**
  - Multi-language support
  - Custom styling per VRP
  - Batch report generation
  - Report scheduling
  - Email delivery integration

- **Performance Optimization:**
  - Redis caching for distributed systems
  - Parallel report generation
  - Streaming large PDFs
  - Async batch operations

- **Integration:**
  - CI/CD pipeline integration
  - Webhook notifications
  - External API integration
  - Custom middleware

---

## Support & Documentation

- **Generated Reports:** `./phase6_verification_report.json`
- **Integration Tests:** `./tests/test_phase6_integration.py`
- **API Endpoints:** `./apps/backend/src/routers/reports.py`
- **Core Modules:** `./apps/backend/src/core/`
  - `report_formats.py` - Jinja2 rendering
  - `pdf_generator.py` - PDF generation
  - `format_exporter.py` - Multi-format export
  - `report_validator.py` - Validation engine
  - `evidence_embedder.py` - Evidence tracking

---

**Phase 6 User Guide v1.0**
Last Updated: February 2, 2026
