# EyeWitness Advanced Techniques

## Baseline Command
```bash
eyewitness --web -f hosts.txt --directory artifacts/eyewitness --timeout 10 --delay 2
```

## Report Reusability
Persist report paths in handoff metadata so analysts can revisit evidence after autonomous phases complete.

## Dual-Engine Strategy
Run EyeWitness and GoWitness together; rendering differences can reveal additional routes, auth flows, or JS-dependent behavior.

## Triage Heuristics
Prioritize pages showing admin/login/debug indicators or unusual status codes.
