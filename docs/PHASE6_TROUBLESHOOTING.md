# Phase 6: Report Generation - Troubleshooting Guide

Common issues and solutions for Phase 6 report generation system.

---

## Installation Issues

### Problem: ModuleNotFoundError when importing core modules

**Symptoms:**
```
ModuleNotFoundError: No module named 'core.pdf_generator'
ModuleNotFoundError: No module named 'core.format_exporter'
```

**Causes:**
- Phase 6 modules not installed
- Python path not configured correctly
- Old cached modules

**Solutions:**

1. **Install/Update dependencies:**
   ```bash
   pip install -r requirements.txt --upgrade
   ```

2. **Verify modules exist:**
   ```bash
   ls -la apps/backend/src/core/{pdf_generator,format_exporter,evidence_embedder,report_validator}.py
   ```

3. **Clear Python cache:**
   ```bash
   find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null
   find . -type f -name "*.pyc" -delete
   ```

4. **Verify PYTHONPATH:**
   ```python
   import sys
   sys.path.insert(0, '/path/to/apps/backend/src')
   from core.pdf_generator import generate_pdf_from_markdown
   ```

---

## PDF Generation Issues

### Problem: PDF generation returns empty or corrupted file

**Symptoms:**
- `len(pdf_bytes) == 0`
- PDF file cannot be opened in reader
- "File is damaged or corrupted" error

**Causes:**
- weasyprint not installed or broken
- Invalid HTML input
- System font issues
- Memory limitations

**Solutions:**

1. **Check weasyprint installation:**
   ```bash
   pip install weasyprint --upgrade
   pip show weasyprint
   ```

2. **Test with minimal content:**
   ```python
   from core.pdf_generator import generate_pdf_from_markdown

   simple_md = "# Test\n\nSimple content"
   pdf = generate_pdf_from_markdown(simple_md)
   print(f"PDF size: {len(pdf)} bytes")
   ```

3. **Check for invalid characters:**
   ```python
   # Avoid special characters in markdown
   markdown = markdown.encode('utf-8', errors='ignore').decode('utf-8')
   ```

4. **Enable logging:**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   pdf = generate_pdf_from_markdown(markdown)
   ```

5. **Reduce content complexity:**
   - Remove large images
   - Simplify table structures
   - Reduce code block size

---

## Template Rendering Issues

### Problem: Template rendering fails with TemplateError

**Symptoms:**
```
jinja2.exceptions.TemplateError: ...
jinja2.exceptions.UndefinedError: ...
jinja2.exceptions.SyntaxError: ...
```

**Causes:**
- Missing template variables
- Invalid Jinja2 syntax
- Special characters in data
- Incompatible data types

**Solutions:**

1. **Verify all required fields present:**
   ```python
   from core.report_formats import build_template_context

   context = build_template_context(finding, evidence, mitigation)
   print("Available variables:", context.keys())
   ```

2. **Check for None values:**
   ```python
   # Ensure all finding fields are non-None
   finding = {
       "title": finding.get("title", ""),
       "severity": finding.get("severity", "unknown"),
       "summary": finding.get("summary", ""),
       # ... all required fields
   }
   ```

3. **Escape special characters:**
   ```python
   import html
   finding["summary"] = html.escape(finding["summary"])
   ```

4. **Validate template syntax:**
   ```python
   from jinja2 import Template
   try:
       t = Template(template_string)
   except Exception as e:
       print(f"Template error: {e}")
   ```

---

## Validation Issues

### Problem: Validation always returns low compliance score

**Symptoms:**
- Compliance score <70
- Multiple warnings
- Recommendations not actionable

**Causes:**
- Required sections missing or misspelled
- Insufficient word count
- Missing evidence
- No reproduction steps

**Solutions:**

1. **Check required sections:**
   ```python
   result = validate_report("google_vrp", content)
   for error in result['errors']:
       print(f"Missing: {error['section']}")
   ```

2. **Increase word counts:**
   ```python
   # Summary needs minimum 50 words for Google VRP
   summary = "A" * 300  # Ensure sufficient words
   content = f"## Summary\n{summary}\n\n## Impact\n..."
   ```

3. **Add reproduction steps:**
   ```python
   repro = """## Steps to Reproduce
   1. First detailed step
   2. Second detailed step
   3. Third detailed step
   """
   ```

4. **Include evidence markers:**
   ```python
   content = """
   ## Evidence
   - Screenshots: proof_1.png, proof_2.png
   - Code example: vulnerable code snippet
   - Error logs: application_error.log
   """
   ```

5. **Review recommendations:**
   ```python
   for rec in result['recommendations']:
       print(f"Fix: {rec}")
   ```

---

## Multi-Format Export Issues

### Problem: Export fails or returns incomplete data

**Symptoms:**
- Some formats missing from export_all result
- Export returns None or empty
- Inconsistent content across formats

**Causes:**
- Invalid finding/evidence/mitigation data
- Missing format dependencies
- Encoding issues
- Insufficient memory

**Solutions:**

1. **Verify input data structure:**
   ```python
   required = ["title", "severity", "summary", "impact"]
   for field in required:
       if field not in finding:
           raise ValueError(f"Missing field: {field}")
   ```

2. **Test single format first:**
   ```python
   exporter = create_exporter("google_vrp")

   # Test markdown first
   md = exporter.export(finding, evidence, mitigation, "markdown")
   if not md:
       raise ValueError("Markdown export failed")
   ```

3. **Check encoding:**
   ```python
   # Ensure content is properly encoded
   for key, value in finding.items():
       if isinstance(value, str):
           finding[key] = value.encode('utf-8', errors='ignore').decode('utf-8')
   ```

4. **Monitor memory usage:**
   ```python
   import psutil
   process = psutil.Process()
   print(f"Memory: {process.memory_info().rss / 1024 / 1024:.1f} MB")
   ```

---

## Evidence Embedding Issues

### Problem: Evidence embedding fails or integrity verification fails

**Symptoms:**
```
Evidence embedding failed: ...
Integrity verification failed: invalid
Evidence not found or expired
```

**Causes:**
- File not found
- Invalid content format
- Corruption in chain
- Merkle verification failed

**Solutions:**

1. **Verify file exists:**
   ```python
   from pathlib import Path

   file_path = Path("evidence.png")
   if not file_path.exists():
       raise FileNotFoundError(f"Not found: {file_path}")
   ```

2. **Check content validity:**
   ```python
   # For images
   from PIL import Image
   try:
       img = Image.open(file_path)
       img.verify()
   except Exception as e:
       raise ValueError(f"Invalid image: {e}")
   ```

3. **Verify merkle chain:**
   ```python
   embedder = create_embedder()

   # Check all evidence in chain
   manifest = embedder.get_evidence_manifest()
   for item in manifest['evidence_list']:
       verification = embedder.verify_evidence_integrity(item['evidence_id'])
       if not verification['valid']:
           print(f"Chain broken at: {item['evidence_id']}")
   ```

4. **Compress images to reduce size:**
   ```python
   from PIL import Image

   img = Image.open("large_screenshot.png")
   img.thumbnail((1920, 1080))
   img.save("compressed.png", quality=85, optimize=True)
   ```

---

## API Endpoint Issues

### Problem: API endpoint returns 500 error

**Symptoms:**
```
500 Internal Server Error
{"detail": "endpoint failed"}
```

**Causes:**
- Authentication failed
- Invalid request format
- Missing dependencies
- Unhandled exception

**Solutions:**

1. **Verify authentication:**
   ```bash
   # Check Authorization header
   curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/reports/cache/stats

   # If 401, regenerate token
   ```

2. **Validate request format:**
   ```bash
   # Use -v flag to see full request/response
   curl -v -X POST http://localhost:8000/reports/generate-all \
     -H "Content-Type: application/json" \
     -d '{...}'
   ```

3. **Check server logs:**
   ```bash
   tail -f logs/reports.log
   tail -f logs/api.log
   ```

4. **Test with curl:**
   ```bash
   curl -X GET http://localhost:8000/reports/cache/stats \
     -H "Authorization: Bearer token" \
     -v  # Verbose output
   ```

---

## Cache Issues

### Problem: Cache not working or reports not found

**Symptoms:**
- GET /reports/cache/{report_id} returns 404
- Cache statistics show 0 reports
- Reports expire too quickly

**Causes:**
- Report expired from cache
- Cache TTL too short
- Report ID incorrect
- Cache not initialized

**Solutions:**

1. **Check cache status:**
   ```python
   from routers.reports import _report_cache, _cache_expiry
   from datetime import datetime

   print(f"Reports in cache: {len(_report_cache)}")
   for rid, expiry in _cache_expiry.items():
       is_expired = datetime.utcnow() > expiry
       print(f"  {rid}: {'EXPIRED' if is_expired else 'ACTIVE'}")
   ```

2. **Verify report ID format:**
   ```
   Expected: REPORT_STAKEHOLDER_TIMESTAMP_HASH
   Example:  REPORT_GOOGLE_VRP_20260202_a1b2c3d4
   ```

3. **Increase TTL:**
   ```python
   # In routers/reports.py
   CACHE_TTL_MINUTES = 120  # Increase from 60
   ```

4. **Manually cache report:**
   ```python
   from routers.reports import _cache_report

   report_id = "REPORT_GOOGLE_VRP_20260202_a1b2c3d4"
   report_data = {"ok": True, "result": {...}}
   _cache_report(report_id, report_data)
   ```

---

## Performance Issues

### Problem: Report generation is slow

**Symptoms:**
- PDF generation takes >5 seconds
- Validation runs slowly
- API endpoints timeout

**Causes:**
- Large content (>100KB)
- Complex images
- System overload
- Inefficient queries

**Solutions:**

1. **Check content size:**
   ```python
   content = exporter.export(finding, evidence, mitigation, "markdown")
   size_kb = len(content) / 1024
   print(f"Content size: {size_kb:.1f} KB")

   if size_kb > 100:
       print("Content too large, consider breaking into sections")
   ```

2. **Optimize images:**
   ```python
   # Compress before embedding
   from PIL import Image
   img = Image.open("screenshot.png")
   img.thumbnail((1920, 1080))
   img.save("optimized.png", quality=85, optimize=True)
   ```

3. **Monitor system resources:**
   ```bash
   # Linux
   top -p PID
   ps aux | grep python

   # macOS
   top -pid PID
   ```

4. **Use async generation:**
   ```python
   # For API requests
   POST /reports/generate-all
   {
       "async_generation": true
   }
   ```

5. **Profile code:**
   ```python
   import cProfile
   import pstats

   profiler = cProfile.Profile()
   profiler.enable()

   # Your code here
   generate_pdf_from_markdown(markdown)

   profiler.disable()
   stats = pstats.Stats(profiler)
   stats.sort_stats('cumulative').print_stats(20)
   ```

---

## Compatibility Issues

### Problem: Reports differ across formats or stakeholder specifications

**Symptoms:**
- Markdown and PDF content differs
- Google VRP format differs from template
- Special characters not rendering

**Causes:**
- Format-specific rules
- Character encoding issues
- Template version mismatch
- Stakeholder-specific requirements

**Solutions:**

1. **Verify format rules:**
   ```python
   from core.report_validator import STAKEHOLDER_RULES

   rules = STAKEHOLDER_RULES['google_vrp']
   print("Required sections:", rules['required_sections'])
   print("Min summary:", rules['min_summary_words'])
   ```

2. **Check character encoding:**
   ```python
   # Ensure UTF-8 encoding
   content = content.encode('utf-8', errors='replace').decode('utf-8')
   ```

3. **Verify template loading:**
   ```python
   from core.report_formats import get_format

   fmt = get_format('google_vrp')
   print("Template loaded:", bool(fmt.get('template')))
   print("Stakeholder:", fmt.get('stakeholder'))
   ```

---

## Testing & Verification

### Run Verification Script

Test all Phase 6 functionality:

```bash
python scripts/verify_phase6_reports.py
```

**Output should show:**
```
✅ PASS - Template Rendering
✅ PASS - PDF Generation
✅ PASS - Multi-Format Export
✅ PASS - Format Validation
✅ PASS - Multiplier Detection
✅ PASS - Evidence Embedding
✅ PASS - Performance Benchmarking
```

### Run Integration Tests

```bash
pytest tests/test_phase6_integration.py -v
```

### Generate Sample Report

```bash
python scripts/verify_phase6_reports.py
# Outputs: phase6_verification_report.json
```

---

## Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('phase6_debug.log'),
        logging.StreamHandler()
    ]
)
```

---

## Common Errors Reference

| Error | Cause | Fix |
|-------|-------|-----|
| `TemplateError: no filter named 'X'` | Missing Jinja2 filter | Update template |
| `PDFError: ...` | weasyprint issue | Reinstall weasyprint |
| `ValidationError: ...` | Invalid finding data | Check data structure |
| `KeyError: 'finding'` | Missing context key | Verify build_template_context |
| `JSONDecodeError: ...` | Invalid JSON export | Check json format output |
| `FileNotFoundError: ...` | File missing | Verify file path |
| `MemoryError` | Out of memory | Process large files in chunks |

---

## Getting Help

1. **Check logs:**
   ```bash
   tail -f logs/reports.log
   ```

2. **Enable debug mode:**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

3. **Review documentation:**
   - User Guide: `docs/PHASE6_USER_GUIDE.md`
   - API Reference: `docs/PHASE6_API_REFERENCE.md`
   - Source Code: `apps/backend/src/core/`

4. **Run tests:**
   ```bash
   pytest tests/test_phase6_integration.py -v --tb=short
   ```

5. **Contact support:**
   - Include error message and logs
   - Provide minimal reproduction case
   - Share relevant code snippet

---

**Troubleshooting Guide v1.0**
Last Updated: February 2, 2026
