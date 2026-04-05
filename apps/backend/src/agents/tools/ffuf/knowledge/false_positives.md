# FFUF False Positives

## Wildcard Responses
Some stacks return uniform responses for invalid paths, creating large false-positive sets.

## VHost Edge Behavior
Default virtual host responses can appear as valid hits across many fuzzed hostnames.

## CDN/Error Normalization
Edge infrastructure may normalize error responses into status codes that appear valid.

## Mitigation
Use response-length clustering and baseline controls; re-validate candidates with secondary probes.
