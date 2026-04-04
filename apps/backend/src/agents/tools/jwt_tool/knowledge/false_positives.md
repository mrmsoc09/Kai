# jwt_tool — False Positives

## HTTP 200 ≠ Authentication Bypass
Some servers return HTTP 200 with an error message body for invalid tokens. A 200 response alone does NOT confirm bypass.

**Verification steps:**
1. Modify token to contain a different user ID or elevated role
2. Use the modified token to access an auth-protected endpoint
3. Verify the response contains protected data (not just a success status)
4. Only then is the finding confirmed

## Algorithm Confusion Preconditions
Algorithm confusion only works if:
- Server uses RS256 (asymmetric) in normal operation
- AND server can be tricked into validating with HS256 using the public key as secret

Verify the server's normal algorithm before assuming confusion is possible.

## Brute Force Context
A cracked HMAC secret is only critical if the secret is used in production. Test environments with weak secrets are lower severity.
