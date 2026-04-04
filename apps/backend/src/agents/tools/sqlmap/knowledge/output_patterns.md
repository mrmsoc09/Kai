# sqlmap — Output Patterns

## Confirmed SQLi Output
sqlmap shows:
- Target URL
- Vulnerable parameter name
- Injection type (boolean-based blind, error-based, UNION-based)
- Back-end DBMS (MySQL, PostgreSQL, MSSQL, Oracle, etc.)

## What to Report
1. Vulnerable URL
2. Parameter name
3. Injection technique
4. Database type

**DO NOT** include dumped data in reports. Discovery is sufficient for most BBP programs.
