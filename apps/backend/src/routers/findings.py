
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from ..core.run_store import load_run, save_run_record
from ..core.auth import require_roles, ROLE_OPERATOR

# Phase 4: Detection module imports
try:
    from modules.detection import (
        FindingDeduplicator,
        EvidenceTracker,
        FindingAnalyzer,
        NucleiScanner,
    )
    DETECTION_AVAILABLE = True
except ImportError:
    DETECTION_AVAILABLE = False

# Phase 5: Patching module imports
try:
    from modules.patching import (
        PatchGenerator,
        PackageAnalyzer,
        PatchValidator,
        RemediationEngine,
    )
    PATCHING_AVAILABLE = True
except ImportError:
    PATCHING_AVAILABLE = False

import json
from pathlib import Path

router = APIRouter(prefix="/findings", tags=["findings"])

# Initialize Phase 4 components
_deduplicator = None
_evidence_tracker = None
_analyzer = None
_nuclei_scanner = None

def _get_detection_components():
    global _deduplicator, _evidence_tracker, _analyzer, _nuclei_scanner
    if DETECTION_AVAILABLE:
        if _deduplicator is None:
            _deduplicator = FindingDeduplicator()
        if _evidence_tracker is None:
            _evidence_tracker = EvidenceTracker()
        if _analyzer is None:
            _analyzer = FindingAnalyzer()
        if _nuclei_scanner is None:
            _nuclei_scanner = NucleiScanner()
    return _deduplicator, _evidence_tracker, _analyzer, _nuclei_scanner

# Initialize Phase 5 components
_patch_generator = None
_package_analyzer = None
_patch_validator = None
_remediation_engine = None

def _get_patching_components():
    global _patch_generator, _package_analyzer, _patch_validator, _remediation_engine
    if PATCHING_AVAILABLE:
        if _patch_generator is None:
            _patch_generator = PatchGenerator()
        if _package_analyzer is None:
            _package_analyzer = PackageAnalyzer()
        if _patch_validator is None:
            _patch_validator = PatchValidator()
        if _remediation_engine is None:
            _remediation_engine = RemediationEngine()
    return _patch_generator, _package_analyzer, _patch_validator, _remediation_engine

# Patching storage directory
PATCHING_DIR = Path(__file__).resolve().parent.parent.parent.parent / 'artifacts' / 'patching'
PLANS_DIR = PATCHING_DIR / 'plans'
PATCHES_DIR = PATCHING_DIR / 'patches'

def _init_patching_dirs():
    """Initialize patching artifact directories."""
    if PATCHING_AVAILABLE:
        PATCHING_DIR.mkdir(parents=True, exist_ok=True)
        PLANS_DIR.mkdir(parents=True, exist_ok=True)
        PATCHES_DIR.mkdir(parents=True, exist_ok=True)

def _save_remediation_plan(plan_id: str, plan: Dict[str, Any]):
    """Persist remediation plan to disk."""
    _init_patching_dirs()
    plan_dir = PLANS_DIR / plan_id
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plan_dir / 'plan.json'
    plan_file.write_text(json.dumps(plan, indent=2))

def _load_remediation_plan(plan_id: str) -> Optional[Dict[str, Any]]:
    """Load remediation plan from disk."""
    plan_file = PLANS_DIR / plan_id / 'plan.json'
    if plan_file.exists():
        return json.loads(plan_file.read_text())
    return None

def _save_remediation_execution(plan_id: str, execution: Dict[str, Any]):
    """Save remediation phase execution record."""
    _init_patching_dirs()
    plan_dir = PLANS_DIR / plan_id
    plan_dir.mkdir(parents=True, exist_ok=True)
    execution_file = plan_dir / 'execution.jsonl'
    with open(execution_file, 'a') as f:
        f.write(json.dumps(execution) + '\n')

@router.post('/set_status')
def set_status(payload: Dict[str, Any]) -> Dict[str, Any]:
    run_id = payload.get('run_id')
    status = (payload.get('status') or '').upper()
    finding_id = payload.get('finding_id') or 'run'
    recording_path = payload.get('recording_path')

    if not run_id or not status:
        raise HTTPException(status_code=400, detail='run_id and status required')

    run = load_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail='run_not_found')

    # Enforce evidence gate: VALIDATED requires recording reference
    if status == 'VALIDATED':
        recorded = recording_path or (run.get('artifacts') or {}).get('recording_path')
        if not recorded:
            return JSONResponse(status_code=409, content={
                'status': 'blocked',
                'reason': 'recording_required',
                'next': 'attach recording_path and retry or keep status below VALIDATED'
            })
        # persist recording into artifacts if provided
        if recording_path:
            run.setdefault('artifacts', {})['recording_path'] = recording_path
            run['first_validated_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    # Update findings list
    fins = run.setdefault('findings', [])
    updated = False
    for f in fins:
        if f.get('id') == finding_id:
            f['status'] = status
            f['updated_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            updated = True
            break
    if not updated:
        fins.append({'id': finding_id, 'status': status, 'updated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')})

    # If this is the first non-INFO status treat as first_signal_at
    if status in ('HYPOTHESIS','SIGNAL','LIKELY') and not run.get('first_signal_at'):
        run['first_signal_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    # Persist updated run (recomputes metrics)
    save_run_record(run_id, run)
    return {'ok': True, 'run_id': run_id, 'findings': fins, 'artifacts': run.get('artifacts', {})}


# ============================================================================
# PHASE 4: VULNERABILITY DETECTION & FINDING MANAGEMENT
# ============================================================================

@router.post('/detection/deduplicate')
async def deduplicate_findings(
    payload: Dict[str, Any],
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Deduplicate findings using multiple strategies.

    Strategies: exact, shallow, fuzzy, multi
    """
    if not DETECTION_AVAILABLE:
        raise HTTPException(503, 'Detection module not available')

    findings = payload.get('findings', [])
    strategy = payload.get('strategy', 'multi')

    if not findings:
        raise HTTPException(400, 'findings required')

    if strategy not in ['exact', 'shallow', 'fuzzy', 'multi']:
        raise HTTPException(400, 'Invalid strategy')

    dedup, _, _, _ = _get_detection_components()
    result = dedup.deduplicate(findings, strategy=strategy)

    return {
        'ok': True,
        'unique_findings': result['unique_findings'],
        'duplicate_groups': result['duplicate_groups'],
        'dedup_summary': result['dedup_summary'],
        'strategy_used': strategy,
    }


@router.post('/detection/analyze')
async def analyze_findings(
    payload: Dict[str, Any],
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Analyze findings for severity, exploitability, and impact.
    """
    if not DETECTION_AVAILABLE:
        raise HTTPException(503, 'Detection module not available')

    findings = payload.get('findings', [])
    context = payload.get('context', {})

    if not findings:
        raise HTTPException(400, 'findings required')

    _, _, analyzer, _ = _get_detection_components()
    analyzed = analyzer.batch_analyze(findings, context)

    return {
        'ok': True,
        'analyzed_findings': analyzed,
        'summary': analyzer.get_analysis_summary(),
    }


@router.post('/detection/analyze-single')
async def analyze_single_finding(
    payload: Dict[str, Any],
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Analyze a single finding for severity, CVSS score, and recommendations.
    """
    if not DETECTION_AVAILABLE:
        raise HTTPException(503, 'Detection module not available')

    finding = payload.get('finding', {})
    context = payload.get('context', {})

    if not finding:
        raise HTTPException(400, 'finding required')

    _, _, analyzer, _ = _get_detection_components()
    analysis = analyzer.analyze_finding(finding, context)

    return {
        'ok': True,
        'analysis': analysis,
    }


@router.post('/detection/prioritize')
async def prioritize_findings(
    payload: Dict[str, Any],
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Prioritize findings by severity, exploitability, or payout.

    Strategies: severity, exploitability, impact, payout, exploitability_impact
    """
    if not DETECTION_AVAILABLE:
        raise HTTPException(503, 'Detection module not available')

    findings = payload.get('findings', [])
    strategies = payload.get('strategies', ['severity', 'exploitability', 'payout'])

    if not findings:
        raise HTTPException(400, 'findings required')

    _, _, analyzer, _ = _get_detection_components()
    prioritized = analyzer.prioritize_findings(findings, strategies)

    return {
        'ok': True,
        'prioritized': prioritized,
    }


@router.post('/detection/evidence/record')
async def record_evidence(
    payload: Dict[str, Any],
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Record evidence with cryptographic integrity tracking.

    Evidence types: scan_output, screenshot, metadata, analysis, validation
    """
    if not DETECTION_AVAILABLE:
        raise HTTPException(503, 'Detection module not available')

    evidence_type = payload.get('type', 'analysis')
    content = payload.get('content', {})
    source = payload.get('source', 'api')
    finding_id = payload.get('finding_id')

    _, tracker, _, _ = _get_detection_components()
    evidence = tracker.record_evidence(evidence_type, content, source, finding_id)

    return {
        'ok': True,
        'evidence': evidence,
    }


@router.get('/detection/evidence/trail/{finding_id}')
async def get_evidence_trail(
    finding_id: str,
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Get evidence trail for a finding.
    """
    if not DETECTION_AVAILABLE:
        raise HTTPException(503, 'Detection module not available')

    _, tracker, _, _ = _get_detection_components()
    trail = tracker.get_evidence_trail(finding_id)

    return {
        'ok': True,
        'finding_id': finding_id,
        'evidence_count': len(trail),
        'trail': trail,
    }


@router.get('/detection/evidence/report/{finding_id}')
async def get_evidence_report(
    finding_id: str,
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Get integrity report for finding's evidence.
    """
    if not DETECTION_AVAILABLE:
        raise HTTPException(503, 'Detection module not available')

    _, tracker, _, _ = _get_detection_components()
    report = tracker.create_evidence_report(finding_id)

    return {
        'ok': True,
        'report': report,
    }


@router.get('/detection/evidence/verify/{evidence_id}')
async def verify_evidence(
    evidence_id: str,
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Verify evidence integrity.
    """
    if not DETECTION_AVAILABLE:
        raise HTTPException(503, 'Detection module not available')

    _, tracker, _, _ = _get_detection_components()
    verification = tracker.verify_evidence_integrity(evidence_id)

    return {
        'ok': True,
        'verification': verification,
    }


@router.get('/detection/nuclei/validate')
async def validate_nuclei_setup(
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Validate Nuclei scanner setup.
    """
    if not DETECTION_AVAILABLE:
        raise HTTPException(503, 'Detection module not available')

    _, _, _, nuclei = _get_detection_components()
    validation = nuclei.validate_nuclei_setup()

    return {
        'ok': True,
        'validation': validation,
    }


@router.post('/detection/nuclei/scan')
async def nuclei_scan(
    payload: Dict[str, Any],
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Scan target with Nuclei.
    """
    if not DETECTION_AVAILABLE:
        raise HTTPException(503, 'Detection module not available')

    target = payload.get('target')
    if not target:
        raise HTTPException(400, 'target required')

    templates = payload.get('templates')
    severity = payload.get('severity', 'medium')
    timeout = payload.get('timeout', 300)

    _, _, _, nuclei = _get_detection_components()
    scan_result = nuclei.scan_target(target, templates, severity, timeout)

    return {
        'ok': True,
        'scan': scan_result,
    }


@router.post('/detection/nuclei/scan-batch')
async def nuclei_scan_batch(
    payload: Dict[str, Any],
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Scan multiple targets with Nuclei.
    """
    if not DETECTION_AVAILABLE:
        raise HTTPException(503, 'Detection module not available')

    targets = payload.get('targets', [])
    if not targets:
        raise HTTPException(400, 'targets required')

    templates = payload.get('templates')
    severity = payload.get('severity', 'medium')

    _, _, _, nuclei = _get_detection_components()
    results = nuclei.scan_batch(targets, templates, severity)

    return {
        'ok': True,
        'results': results,
    }


@router.get('/detection/nuclei/templates')
async def list_nuclei_templates(
    category: Optional[str] = None,
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    List available Nuclei templates.
    """
    if not DETECTION_AVAILABLE:
        raise HTTPException(503, 'Detection module not available')

    _, _, _, nuclei = _get_detection_components()
    templates = nuclei.list_templates(category)

    return {
        'ok': True,
        'templates': templates,
    }


@router.get('/detection/nuclei/stats')
async def get_nuclei_stats(
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Get Nuclei scanning statistics.
    """
    if not DETECTION_AVAILABLE:
        raise HTTPException(503, 'Detection module not available')

    _, _, _, nuclei = _get_detection_components()
    stats = nuclei.get_scan_stats()

    return {
        'ok': True,
        'stats': stats,
    }


@router.get('/detection/stats')
async def get_detection_stats(
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Get overall detection module statistics.
    """
    if not DETECTION_AVAILABLE:
        raise HTTPException(503, 'Detection module not available')

    dedup, tracker, analyzer, nuclei = _get_detection_components()

    return {
        'ok': True,
        'deduplicator_stats': dedup.get_dedup_stats(),
        'evidence_chain_stats': tracker.get_chain_stats(),
        'analysis_summary': analyzer.get_analysis_summary(),
        'nuclei_stats': nuclei.get_scan_stats(),
    }


# ============================================================================
# PHASE 5: PATCH ENGINE & REMEDIATION
# ============================================================================

# ============================================================================
# PHASE 5: PATCH GENERATION
# ============================================================================

@router.post('/patching/patches/generate')
async def generate_patch(
    payload: Dict[str, Any],
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Generate a patch suggestion for a finding.
    """
    if not PATCHING_AVAILABLE:
        raise HTTPException(503, 'Patching module not available')

    finding = payload.get('finding')
    context = payload.get('context', {})

    if not finding:
        raise HTTPException(400, 'finding required')

    generator, _, _, _ = _get_patching_components()
    patch = generator.generate_patch(finding, context)

    return {
        'ok': True,
        'patch': patch,
    }


@router.post('/patching/patches/generate-batch')
async def generate_batch_patches(
    payload: Dict[str, Any],
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Generate patch suggestions for multiple findings.
    """
    if not PATCHING_AVAILABLE:
        raise HTTPException(503, 'Patching module not available')

    findings = payload.get('findings', [])
    context = payload.get('context', {})

    if not findings:
        raise HTTPException(400, 'findings required')

    generator, _, _, _ = _get_patching_components()
    patches = generator.generate_batch_patches(findings, context)

    return {
        'ok': True,
        'patches': patches,
        'count': len(patches),
    }


@router.post('/patching/patches/prioritize')
async def prioritize_patches(
    payload: Dict[str, Any],
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Prioritize patches by strategy.

    Strategies: impact, effort, roi, time
    """
    if not PATCHING_AVAILABLE:
        raise HTTPException(503, 'Patching module not available')

    patches = payload.get('patches', [])
    strategy = payload.get('strategy', 'impact')

    if not patches:
        raise HTTPException(400, 'patches required')

    if strategy not in ['impact', 'effort', 'roi', 'time']:
        raise HTTPException(400, 'Invalid strategy')

    generator, _, _, _ = _get_patching_components()
    prioritized = generator.prioritize_patches(patches, strategy)

    return {
        'ok': True,
        'prioritized': prioritized,
        'strategy': strategy,
    }


@router.get('/patching/patches/{finding_id}')
async def get_patch(
    finding_id: str,
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Get a generated patch by finding ID.
    """
    if not PATCHING_AVAILABLE:
        raise HTTPException(503, 'Patching module not available')

    generator, _, _, _ = _get_patching_components()
    patch = generator.get_patch_by_id(finding_id)

    if not patch:
        raise HTTPException(404, 'Patch not found')

    return {
        'ok': True,
        'patch': patch,
    }


@router.post('/patching/patches/estimate-impact')
async def estimate_patch_impact(
    payload: Dict[str, Any],
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Estimate the impact and risk of applying a patch.
    """
    if not PATCHING_AVAILABLE:
        raise HTTPException(503, 'Patching module not available')

    patch = payload.get('patch')

    if not patch:
        raise HTTPException(400, 'patch required')

    generator, _, _, _ = _get_patching_components()
    impact = generator.estimate_patch_impact(patch)

    return {
        'ok': True,
        'impact': impact,
    }


@router.get('/patching/patches/stats')
async def get_patch_stats(
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Get patch generation statistics.
    """
    if not PATCHING_AVAILABLE:
        raise HTTPException(503, 'Patching module not available')

    generator, _, _, _ = _get_patching_components()
    stats = generator.get_patch_stats()

    return {
        'ok': True,
        'stats': stats,
    }


# ============================================================================
# PHASE 5: PACKAGE ANALYSIS
# ============================================================================

@router.post('/patching/packages/analyze')
async def analyze_package(
    payload: Dict[str, Any],
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Analyze a package for vulnerabilities.
    """
    if not PATCHING_AVAILABLE:
        raise HTTPException(503, 'Patching module not available')

    package_name = payload.get('package_name')
    version = payload.get('version')

    if not package_name or not version:
        raise HTTPException(400, 'package_name and version required')

    _, analyzer, _, _ = _get_patching_components()
    analysis = analyzer.analyze_package(package_name, version)

    return {
        'ok': True,
        'analysis': analysis,
    }


@router.post('/patching/packages/analyze-requirements')
async def analyze_requirements(
    payload: Dict[str, Any],
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Analyze all packages in requirements.

    Payload: {'requirements': {'package_name': 'version', ...}}
    """
    if not PATCHING_AVAILABLE:
        raise HTTPException(503, 'Patching module not available')

    requirements = payload.get('requirements', {})

    if not requirements:
        raise HTTPException(400, 'requirements required')

    _, analyzer, _, _ = _get_patching_components()
    analysis = analyzer.analyze_requirements(requirements)

    return {
        'ok': True,
        'analysis': analysis,
    }


@router.post('/patching/packages/upgrade-path')
async def get_upgrade_path(
    payload: Dict[str, Any],
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Get upgrade path for a vulnerable package.
    """
    if not PATCHING_AVAILABLE:
        raise HTTPException(503, 'Patching module not available')

    package_name = payload.get('package_name')
    version = payload.get('version')

    if not package_name or not version:
        raise HTTPException(400, 'package_name and version required')

    _, analyzer, _, _ = _get_patching_components()
    upgrade_path = analyzer.get_upgrade_path(package_name, version)

    return {
        'ok': True,
        'upgrade_path': upgrade_path,
    }


@router.post('/patching/packages/check-cve')
async def check_cve_status(
    payload: Dict[str, Any],
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Check if a specific CVE is fixed in the current version.
    """
    if not PATCHING_AVAILABLE:
        raise HTTPException(503, 'Patching module not available')

    package_name = payload.get('package_name')
    version = payload.get('version')
    cve_id = payload.get('cve_id')

    if not package_name or not version or not cve_id:
        raise HTTPException(400, 'package_name, version, and cve_id required')

    _, analyzer, _, _ = _get_patching_components()
    status = analyzer.check_cve_status(package_name, version, cve_id)

    return {
        'ok': True,
        'cve_status': status,
    }


@router.get('/patching/packages/stats')
async def get_package_stats(
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Get package analysis statistics.
    """
    if not PATCHING_AVAILABLE:
        raise HTTPException(503, 'Patching module not available')

    _, analyzer, _, _ = _get_patching_components()
    stats = analyzer.get_analyzer_stats()

    return {
        'ok': True,
        'stats': stats,
    }


# ============================================================================
# PHASE 5: PATCH VALIDATION
# ============================================================================

@router.post('/patching/validate/patch')
async def validate_patch(
    payload: Dict[str, Any],
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Validate a patch suggestion for correctness.
    """
    if not PATCHING_AVAILABLE:
        raise HTTPException(503, 'Patching module not available')

    patch = payload.get('patch')
    code_context = payload.get('code_context')
    vulnerability_type = payload.get('vulnerability_type')

    if not patch:
        raise HTTPException(400, 'patch required')

    _, _, validator, _ = _get_patching_components()
    validation = validator.validate_patch(patch, code_context, vulnerability_type)

    return {
        'ok': True,
        'validation': validation,
    }


@router.post('/patching/validate/applicability')
async def validate_applicability(
    payload: Dict[str, Any],
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Check if a patch is applicable to the codebase.
    """
    if not PATCHING_AVAILABLE:
        raise HTTPException(503, 'Patching module not available')

    patch = payload.get('patch')
    codebase_info = payload.get('codebase_info', {})

    if not patch:
        raise HTTPException(400, 'patch required')

    _, _, validator, _ = _get_patching_components()
    applicability = validator.validate_patch_applicability(patch, codebase_info)

    return {
        'ok': True,
        'applicability': applicability,
    }


@router.post('/patching/validate/compatibility')
async def validate_compatibility(
    payload: Dict[str, Any],
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Check if two patches can be applied together.
    """
    if not PATCHING_AVAILABLE:
        raise HTTPException(503, 'Patching module not available')

    old_patch = payload.get('old_patch')
    new_patch = payload.get('new_patch')

    if not old_patch or not new_patch:
        raise HTTPException(400, 'old_patch and new_patch required')

    _, _, validator, _ = _get_patching_components()
    compatibility = validator.validate_patch_compatibility(old_patch, new_patch)

    return {
        'ok': True,
        'compatibility': compatibility,
    }


@router.get('/patching/validate/stats')
async def get_validation_stats(
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Get patch validation statistics.
    """
    if not PATCHING_AVAILABLE:
        raise HTTPException(503, 'Patching module not available')

    _, _, validator, _ = _get_patching_components()
    stats = validator.get_validation_stats()

    return {
        'ok': True,
        'stats': stats,
    }


# ============================================================================
# PHASE 5: REMEDIATION ORCHESTRATION
# ============================================================================

@router.post('/patching/remediation/create-plan')
async def create_remediation_plan(
    payload: Dict[str, Any],
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Create a comprehensive remediation plan for findings.
    """
    if not PATCHING_AVAILABLE:
        raise HTTPException(503, 'Patching module not available')

    findings = payload.get('findings', [])
    patches = payload.get('patches', [])
    context = payload.get('context', {})

    if not findings or not patches:
        raise HTTPException(400, 'findings and patches required')

    _, _, _, engine = _get_patching_components()
    plan = engine.create_remediation_plan(findings, patches, context)

    # Persist plan to disk
    _save_remediation_plan(plan['plan_id'], plan)

    return {
        'ok': True,
        'plan': plan,
    }


@router.post('/patching/remediation/execute-phase')
async def execute_remediation_phase(
    payload: Dict[str, Any],
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Execute a phase of the remediation plan.

    Default: simulated=True (safe, no actual patching)
    """
    if not PATCHING_AVAILABLE:
        raise HTTPException(503, 'Patching module not available')

    plan_id = payload.get('plan_id')
    phase_number = payload.get('phase_number')
    simulated = payload.get('simulated', True)

    if not plan_id or phase_number is None:
        raise HTTPException(400, 'plan_id and phase_number required')

    _, _, _, engine = _get_patching_components()
    execution = engine.execute_remediation_phase(plan_id, phase_number, simulated)

    if 'error' in execution:
        raise HTTPException(404, execution['error'])

    # Persist execution record
    _save_remediation_execution(plan_id, execution)

    return {
        'ok': True,
        'execution': execution,
        'simulated': simulated,
    }


@router.post('/patching/remediation/validate-readiness')
async def validate_readiness(
    payload: Dict[str, Any],
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Validate system is ready for remediation.

    Environment: staging|production (default: staging)
    """
    if not PATCHING_AVAILABLE:
        raise HTTPException(503, 'Patching module not available')

    plan_id = payload.get('plan_id')
    environment = payload.get('environment', 'staging')

    if not plan_id:
        raise HTTPException(400, 'plan_id required')

    _, _, _, engine = _get_patching_components()
    readiness = engine.validate_remediation_readiness(plan_id, environment)

    return {
        'ok': True,
        'readiness': readiness,
    }


@router.post('/patching/remediation/create-tests')
async def create_test_suite(
    payload: Dict[str, Any],
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Create test suite for patches.
    """
    if not PATCHING_AVAILABLE:
        raise HTTPException(503, 'Patching module not available')

    patches = payload.get('patches', [])

    if not patches:
        raise HTTPException(400, 'patches required')

    _, _, _, engine = _get_patching_components()
    test_suite = engine.create_test_suite(patches)

    return {
        'ok': True,
        'test_suite': test_suite,
    }


@router.get('/patching/remediation/report/{plan_id}')
async def get_remediation_report(
    plan_id: str,
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Get comprehensive remediation report.
    """
    if not PATCHING_AVAILABLE:
        raise HTTPException(503, 'Patching module not available')

    _, _, _, engine = _get_patching_components()
    report = engine.generate_remediation_report(plan_id)

    if 'error' in report:
        raise HTTPException(404, report['error'])

    return {
        'ok': True,
        'report': report,
    }


@router.get('/patching/remediation/stats')
async def get_remediation_stats(
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Get remediation statistics.
    """
    if not PATCHING_AVAILABLE:
        raise HTTPException(503, 'Patching module not available')

    _, _, _, engine = _get_patching_components()
    stats = engine.get_remediation_stats()

    return {
        'ok': True,
        'stats': stats,
    }


# ============================================================================
# PHASE 5: UNIFIED STATS
# ============================================================================

@router.get('/patching/stats')
async def get_patching_stats(
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Get overall patching module statistics.
    """
    if not PATCHING_AVAILABLE:
        raise HTTPException(503, 'Patching module not available')

    generator, analyzer, validator, engine = _get_patching_components()

    return {
        'ok': True,
        'patch_generation_stats': generator.get_patch_stats(),
        'package_analysis_stats': analyzer.get_analyzer_stats(),
        'validation_stats': validator.get_validation_stats(),
        'remediation_stats': engine.get_remediation_stats(),
    }
