# Smuggler False Positives

## Inconclusive Detections
Server doesn't respond predictably to ambiguous headers. Doesn't mean vulnerable.

## Proxy-Specific Behavior
Different proxies interpret headers differently. Test result may not apply to actual server.

## WAF Interference
WAF may block smuggling probes. Server itself may not be vulnerable.

## Mitigation
Always manually test positive findings. Proxy behavior variance is known issue.
