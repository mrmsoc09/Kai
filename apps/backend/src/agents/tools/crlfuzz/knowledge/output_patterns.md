# crlfuzz — Output Patterns

## HIGH SIGNAL — Injected Header in Response
```
[Vulnerable] https://target.com/redirect?url=value%0d%0aSet-Cookie:session=attacker
```
- `Set-Cookie` injection = session fixation risk
- `Location` header injection = open redirect + potential XSS

## MEDIUM SIGNAL — Partial Injection
- `%0a` (LF only) reflected without `%0d` (CR)
- Still injectable but less reliable exploit primitive

## LOW SIGNAL
- URL encoding reflected in response **body** (not headers)
- This is reflected content, not header injection

## NOISE
- Empty output for a host = not vulnerable
- Tool tests many endpoints; most return nothing — expected
