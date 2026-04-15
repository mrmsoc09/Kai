-- Analytics Views for Findings Database

-- View: Payout Summary by Program
-- Shows total findings, submissions, payouts, and accuracy per program
CREATE OR REPLACE VIEW payout_summary_by_program AS
SELECT
    f.program_id,
    COUNT(DISTINCT f.id) as total_findings_discovered,
    COUNT(DISTINCT CASE WHEN f.is_duplicate = false THEN f.id END) as unique_findings,
    COUNT(DISTINCT CASE WHEN f.status = 'submitted' THEN f.id END) as submitted_findings,
    COUNT(DISTINCT CASE WHEN f.status = 'accepted' THEN f.id END) as accepted_findings,
    COUNT(DISTINCT CASE WHEN f.status = 'paid' THEN f.id END) as paid_findings,
    COUNT(DISTINCT CASE WHEN f.status = 'rejected' THEN f.id END) as rejected_findings,
    COALESCE(SUM(CASE WHEN f.status = 'paid' THEN f.actual_payout ELSE NULL END), 0) as total_payout_received,
    COALESCE(SUM(CASE WHEN f.status IN ('accepted', 'paid') THEN f.estimated_payout ELSE NULL END), 0) as total_payout_estimated,
    ROUND(
        (COALESCE(SUM(CASE WHEN f.status = 'paid' THEN f.actual_payout ELSE NULL END), 0) /
         NULLIF(COALESCE(SUM(CASE WHEN f.status IN ('accepted', 'paid') THEN f.estimated_payout ELSE NULL END), 0), 0)) * 100,
        2
    ) as payout_accuracy_percentage,
    ROUND(
        (COUNT(DISTINCT CASE WHEN f.status IN ('accepted', 'paid') THEN f.id END) * 100.0 /
         NULLIF(COUNT(DISTINCT CASE WHEN f.is_duplicate = false THEN f.id END), 0)),
        2
    ) as acceptance_rate_percentage,
    ROUND(AVG(CAST(f.ai_confidence_score AS NUMERIC)), 3) as avg_ai_confidence,
    MAX(f.discovered_at) as last_finding_date
FROM findings f
GROUP BY f.program_id;


-- View: Playbook Performance
-- Shows how effective each playbook is at finding valid, accepted, paid vulnerabilities
CREATE OR REPLACE VIEW playbook_performance AS
SELECT
    f.playbook_id,
    f.playbook_name,
    COUNT(DISTINCT f.id) as total_findings,
    COUNT(DISTINCT CASE WHEN f.is_duplicate = false THEN f.id END) as unique_findings,
    COUNT(DISTINCT CASE WHEN f.finding_state = 'valid' THEN f.id END) as valid_findings,
    COUNT(DISTINCT CASE WHEN f.finding_state = 'false_positive' THEN f.id END) as false_positives,
    COUNT(DISTINCT CASE WHEN f.status = 'accepted' THEN f.id END) as accepted_findings,
    COUNT(DISTINCT CASE WHEN f.status = 'paid' THEN f.id END) as paid_findings,
    COALESCE(SUM(CASE WHEN f.status = 'paid' THEN f.actual_payout ELSE NULL END), 0) as total_payout,
    ROUND(
        (COUNT(DISTINCT CASE WHEN f.status = 'accepted' THEN f.id END) * 100.0 /
         NULLIF(COUNT(DISTINCT CASE WHEN f.is_duplicate = false THEN f.id END), 0)),
        2
    ) as acceptance_rate_percentage,
    ROUND(
        (COUNT(DISTINCT CASE WHEN f.status = 'paid' THEN f.id END) * 100.0 /
         NULLIF(COUNT(DISTINCT CASE WHEN f.status = 'accepted' THEN f.id END), 0)),
        2
    ) as payout_rate_percentage,
    ROUND(AVG(CAST(f.cvss_score AS NUMERIC)), 1) as avg_cvss_score,
    ROUND(AVG(CAST(f.ai_confidence_score AS NUMERIC)), 3) as avg_ai_confidence,
    COUNT(DISTINCT f.scan_id) as scan_count,
    MAX(f.discovered_at) as last_used_date
FROM findings f
WHERE f.playbook_id IS NOT NULL
GROUP BY f.playbook_id, f.playbook_name
ORDER BY total_payout DESC;


-- View: Vulnerability Type Distribution
-- Analyzes finding patterns by vulnerability type
CREATE OR REPLACE VIEW vulnerability_distribution AS
SELECT
    vulnerability_type,
    COUNT(*) as total_found,
    COUNT(DISTINCT CASE WHEN is_duplicate = false THEN id END) as unique_count,
    COUNT(DISTINCT program_id) as programs_affected,
    COUNT(DISTINCT scan_id) as found_in_scans,
    ROUND(AVG(CAST(cvss_score AS NUMERIC)), 1) as avg_cvss,
    MAX(CAST(cvss_score AS NUMERIC)) as max_cvss,
    COUNT(DISTINCT CASE WHEN status = 'accepted' THEN id END) as accepted_count,
    COUNT(DISTINCT CASE WHEN status = 'paid' THEN id END) as paid_count,
    ROUND(AVG(CAST(ai_confidence_score AS NUMERIC)), 3) as avg_ai_confidence,
    COALESCE(SUM(CASE WHEN status = 'paid' THEN actual_payout ELSE NULL END), 0) as total_payout,
    ROUND(
        (COUNT(DISTINCT CASE WHEN status IN ('accepted', 'paid') THEN id END) * 100.0 /
         NULLIF(COUNT(DISTINCT CASE WHEN is_duplicate = false THEN id END), 0)),
        2
    ) as acceptance_rate_percentage
FROM findings
GROUP BY vulnerability_type
ORDER BY total_payout DESC;


-- View: Scan Effectiveness Summary
-- Analyzes scan execution efficiency and results
CREATE OR REPLACE VIEW scan_effectiveness_summary AS
SELECT
    s.id as scan_id,
    s.program_id,
    s.scan_name,
    s.scan_type,
    s.workflow_template_used,
    s.triggered_at,
    s.duration_seconds,
    s.status,
    COUNT(DISTINCT f.id) as findings_discovered,
    COUNT(DISTINCT CASE WHEN f.is_duplicate = false THEN f.id END) as unique_findings,
    COUNT(DISTINCT CASE WHEN f.status IN ('accepted', 'paid') THEN f.id END) as valuable_findings,
    COALESCE(SUM(CASE WHEN f.status = 'paid' THEN f.actual_payout ELSE NULL END), 0) as payout_from_scan,
    ROUND(
        COALESCE(SUM(CASE WHEN f.status = 'paid' THEN f.actual_payout ELSE NULL END), 0) /
        NULLIF(s.duration_seconds, 0),
        2
    ) as payout_per_second,
    ROUND(AVG(CAST(f.ai_confidence_score AS NUMERIC)), 3) as avg_ai_confidence,
    ROUND(
        (COUNT(DISTINCT CASE WHEN f.status IN ('accepted', 'paid') THEN f.id END) * 100.0 /
         NULLIF(COUNT(DISTINCT CASE WHEN f.is_duplicate = false THEN f.id END), 0)),
        2
    ) as valuable_rate_percentage
FROM scans s
LEFT JOIN findings f ON s.id = f.scan_id
GROUP BY s.id, s.program_id, s.scan_name, s.scan_type, s.workflow_template_used,
         s.triggered_at, s.duration_seconds, s.status
ORDER BY payout_from_scan DESC;


-- View: Monthly Analytics Summary
-- High-level month-over-month trends
CREATE OR REPLACE VIEW monthly_analytics_summary AS
SELECT
    DATE_TRUNC('month', f.discovered_at)::DATE as month,
    COUNT(DISTINCT f.id) as findings_discovered,
    COUNT(DISTINCT CASE WHEN f.is_duplicate = false THEN f.id END) as unique_findings,
    COUNT(DISTINCT CASE WHEN f.status = 'accepted' THEN f.id END) as accepted_findings,
    COUNT(DISTINCT CASE WHEN f.status = 'paid' THEN f.id END) as paid_findings,
    COALESCE(SUM(CASE WHEN f.status = 'paid' THEN f.actual_payout ELSE NULL END), 0) as total_payout,
    ROUND(AVG(CAST(f.cvss_score AS NUMERIC)), 1) as avg_cvss,
    ROUND(
        (COUNT(DISTINCT CASE WHEN f.status IN ('accepted', 'paid') THEN f.id END) * 100.0 /
         NULLIF(COUNT(DISTINCT CASE WHEN f.is_duplicate = false THEN f.id END), 0)),
        2
    ) as acceptance_rate_percentage
FROM findings f
GROUP BY DATE_TRUNC('month', f.discovered_at)
ORDER BY month DESC;


-- View: Duplicate Analysis
-- Analyze deduplication patterns and effectiveness
CREATE OR REPLACE VIEW duplicate_analysis AS
SELECT
    duplicate_of_finding_id,
    COUNT(*) as duplicate_count,
    ROUND(AVG(CAST(deduplication_confidence AS NUMERIC)), 3) as avg_dedup_confidence,
    MAX(deduplication_reason) as most_common_dedup_reason,
    SUM(CASE WHEN deduplication_reason = 'exact_match' THEN 1 ELSE 0 END) as exact_matches,
    SUM(CASE WHEN deduplication_reason = 'semantic_match' THEN 1 ELSE 0 END) as semantic_matches,
    SUM(CASE WHEN deduplication_reason = 'correlation' THEN 1 ELSE 0 END) as correlations
FROM findings
WHERE is_duplicate = true
GROUP BY duplicate_of_finding_id
ORDER BY duplicate_count DESC;


-- View: Submission Quality Metrics
-- Analyze submission quality and platform feedback
CREATE OR REPLACE VIEW submission_quality_metrics AS
SELECT
    s.submitted_to_platform,
    COUNT(DISTINCT s.id) as total_submissions,
    COUNT(DISTINCT CASE WHEN s.current_status = 'accepted' THEN s.id END) as accepted_submissions,
    COUNT(DISTINCT CASE WHEN s.current_status = 'rejected' THEN s.id END) as rejected_submissions,
    COUNT(DISTINCT CASE WHEN s.current_status = 'paid' THEN s.id END) as paid_submissions,
    ROUND(
        (COUNT(DISTINCT CASE WHEN s.current_status = 'accepted' THEN s.id END) * 100.0 /
         NULLIF(COUNT(DISTINCT s.id), 0)),
        2
    ) as acceptance_rate_percentage,
    ROUND(AVG(CAST(s.report_quality_score AS NUMERIC)), 2) as avg_report_quality_score,
    COALESCE(SUM(s.payout_amount), 0) as total_payout,
    ROUND(AVG(CAST(s.payout_amount AS NUMERIC)), 2) as avg_payout_per_submission,
    MAX(s.submitted_at) as last_submission_date
FROM submissions s
GROUP BY s.submitted_to_platform
ORDER BY total_payout DESC;
