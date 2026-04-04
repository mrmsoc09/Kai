# Smuggler Advanced Techniques

## Detection Methods
TE.CL: Transfer-Encoding vs Content-Length conflict. CL.TE: Opposite order. Smuggler detects both.

## Passive Only
Smuggler detects variants without sending exploit payloads. Never modifies target state.

## Manual Verification Required
Positive result = needs human testing. Different proxy/WAF combinations interpret headers differently. Detection variance common.

## Timeout Handling
Some servers hang on smuggling probes. Timeouts normal. Not false positives—servers blocking.
