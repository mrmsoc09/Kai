# KAISON AI Complete Platform Architecture (Prompts 5-12)

## 1. End-to-End Pipeline
1. Scope authorization and policy enforcement.
2. Detection-only playbook prioritization.
3. Optimized scanning and evidence capture.
4. Deduplication, categorization, severity/payout estimation.
5. AI pattern recognition and inference.
6. Mandatory HiL analyst validation and audit trail.
7. Screen recording + terminal signal validation.
8. Platform submission gateway and status tracking.
9. Daily orchestration (6AM), round-robin cycle, market-intel targeted scans.

## 2. Core Components
### Detection + Optimization (Option B)
- `tools/orchestration/bug_bounty_detection_model.py`
- `tools/orchestration/scanning_prioritization_engine.py`
- `tools/orchestration/bug_bounty_automation_orchestrator.py`
- `tools/intelligence/finding_deduplicator.py`
- `tools/intelligence/finding_categorization.py`
- `tools/intelligence/severity_payout_estimator.py`

### AI + Governance + Submission (Option C)
- `tools/ai/pattern_recognition_engine.py`
- `tools/ai/intelligent_inference_engine.py`
- `tools/ai/learning_feedback_loop.py`
- `tools/hil/hil_review_queue.py`
- `tools/hil/approval_workflow.py`
- `tools/hil/hil_audit_trail.py`
- `tools/submission/finding_submission_gateway.py`
- `tools/submission/screen_recording_validator.py`
- `tools/submission/platform_api_submission.py`

### Prompt 12 Orchestration Layer
- `tools/orchestration/daily_6am_sweep.py`
- `tools/orchestration/round_robin_manager.py`
- `tools/orchestration/scan_queue_balancer.py`
- `tools/intelligence/market_intelligence_engine.py`

## 3. Prompt 12 Design
### Daily 6AM Sweep
- Computes confidence + payout for all opportunities.
- Refreshes market intelligence and targeted-scan triggers.
- Refreshes round-robin queue without duplicating already-scanned items in active cycle.
- Builds balanced daily schedule using dual-queue balancer.
- Writes immutable hash-chained sweep records.

### Round-Robin Cycle Manager
- Maintains active queue of unscanned opportunities.
- Removes opportunities after scan completion.
- Renews cycle only when complete.
- Persists state for restart safety.

### Market Intelligence Engine
- Supports NVD API path (when enabled) and deterministic offline snapshot fallback.
- Supports ExploitDB snapshot path.
- Cross-references opportunities by detected tech stack.
- Emits targeted intelligent scan candidates by CVE impact breadth and severity.

### Scan Queue Balancer
- Dual queues: `round_robin` and `intelligent`.
- Deficit-based fairness with starvation guard.
- Target time budget split: 50/50.
- Event logging for scheduler decisions and completions.

## 4. Governance + Safety Invariants
- Scope validation remains mandatory before active scanning.
- Detection-only operations enforced; no exploitation/persistence/destructive workflows introduced in orchestration layer.
- HiL approval remains blocking before submission.
- Submission remains gated by recording validation + report format + scope confirmation.
- All key orchestration decisions are logged.

## 5. Operational Interfaces
- `DailyOrchestrationSweep.execute_6am_sweep()` for scheduler trigger.
- `RoundRobinCycleManager.mark_opportunity_scanned()` from execution workers.
- `ScanQueueBalancer.schedule_next_scan()` for dispatch loop.
- `MarketIntelligenceEngine.update_market_intelligence_daily()` for daily intel refresh.

## 6. Deployment Notes
- Default market intelligence mode is offline-safe snapshot.
- Live NVD/ExploitDB connectivity can be enabled by runtime config and network policy.
- Submission APIs require platform tokens and reachable network.
