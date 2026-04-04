# SSRFmap — Output Patterns

## HIGH SIGNAL — Full Response Read
- Target fetches attacker URL and returns response body
- Internal IP ranges visible in response: `10.x`, `172.16.x`, `192.168.x`
- Cloud metadata content: `ami-id`, `instance-id`, IAM credential blocks

## MEDIUM SIGNAL — DNS Only
- DNS callback received but no HTTP response body returned
- Confirms SSRF exists but may be blind
- Still reportable — severity depends on what is internally reachable

## LOW SIGNAL / NOISE
- Connection refused (port not open on internal host)
- Timeout (firewall blocking outbound — not necessarily vulnerable)
- No callback received (parameter not used server-side)

## Cloud Metadata Indicators (Critical)
```
iam/security-credentials/
aws_access_key_id
aws_secret_access_key
instance-id
ami-id
```
Any of these in the response = Critical SSRF.
