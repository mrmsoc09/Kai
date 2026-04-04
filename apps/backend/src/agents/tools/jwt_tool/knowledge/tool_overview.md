# jwt_tool — Tool Overview

jwt_tool is a comprehensive JWT (JSON Web Token) security testing toolkit. It tests JWT implementations for algorithm confusion, none algorithm acceptance, weak secret brute force, key injection, and header manipulation attacks.

## Critical Importance
Modern authentication in API-heavy programs like Coinbase and X.com relies on JWTs. A broken JWT implementation typically results in **complete authentication bypass** — high or critical severity.

## Output Format
Plaintext showing attack results, server accept/reject status, and modified token values.

## Input Requirement
Requires a valid JWT token captured from an authenticated session. Obtain from browser localStorage, sessionStorage, or an intercepted authenticated request.

## Pipeline Role
Phase 8 API and auth testing. Requires prior authenticated session to capture the token.
