# GoWitness Advanced Techniques

## Baseline Command
```bash
gowitness scan file -f hosts.txt --screenshot-path artifacts/screenshots --delay 2 --timeout 10
```

## Throughput Control
Delay and timeout settings reduce load and stabilize screenshot quality across large host lists.

## Metadata Preservation
Capture URL, title, status code, and screenshot path in findings for reproducibility.

## Workflow Integration
Use high-interest visual findings to prioritize feroxbuster and nuclei scan queues.
