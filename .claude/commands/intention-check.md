Before proceeding, state the following explicitly:

1. WHAT: What you are about to do (specific action)
2. FILES: Which files will be created or modified (exact paths)
3. BAND: Risk level of this action (Band 0 / 1 / 2 / 3)
4. APPROVAL: Whether human approval is required (yes/no and why)
5. EXPECTED OUTPUT: What will exist after this action completes
6. ROLLBACK: How to undo this action if it causes problems

If Band is 2 or 3, pause and wait for explicit confirmation before executing.
If files include auth/, certs/, secrets/, or .env — pause regardless of band.
