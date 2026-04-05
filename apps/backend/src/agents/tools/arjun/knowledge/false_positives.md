# Arjun False Positives

## Non-Functional Echo Params
Some parameters are accepted but ignored by backend logic.

## Reflection Without State Change
A reflected parameter may look meaningful but not influence any sensitive operation.

## Cache/Proxy Side Effects
Intermediaries can alter apparent response differences.

## Mitigation
Correlate parameter influence over multiple requests and verify behavior changes before escalation.
