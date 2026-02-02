from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from pathlib import Path
import json, time
from ..core.auth import require_roles, ROLE_OPERATOR

router = APIRouter(prefix='/programs', tags=['programs'], dependencies=[Depends(require_roles(ROLE_OPERATOR))])

ROOT = Path(__file__).resolve().parents[4]
PROG_DIR = ROOT / 'artifacts' / 'programs'
PROG_DIR.mkdir(parents=True, exist_ok=True)

@router.post('/ingest_vrp')
async def ingest_vrp(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Plan-only: accept pasted JSON/fields for Google VRP or others; no network fetch
    data = payload.get('data') or {}
    name = data.get('name') or payload.get('name') or 'program'
    slug = (payload.get('slug') or name.lower().replace(' ', '-'))
    program = {
        'slug': slug,
        'name': name,
        'platform': data.get('platform', 'google_vrp'),
        'policy_url': data.get('policy_url'),
        'scope': data.get('scope') or [],
        'rules': data.get('rules') or {},
        'ingested_at': int(time.time())
    }
    outdir = PROG_DIR / slug
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / 'program.json').write_text(json.dumps(program, indent=2))
    return {'ok': True, 'slug': slug, 'path': str(outdir / 'program.json')}

@router.get('/list')
async def list_programs() -> Dict[str, Any]:
    out = []
    for p in PROG_DIR.glob('*/program.json'):
        try:
            out.append(json.loads(p.read_text()))
        except Exception:
            pass
    return {'programs': out}

@router.get('/get/{slug}')
async def get_program(slug: str) -> Dict[str, Any]:
    p = PROG_DIR / slug / 'program.json'
    if not p.exists():
        raise HTTPException(404, 'program not found')
    return json.loads(p.read_text())


from fastapi.responses import FileResponse
from typing import Optional, List

# PHASE 3: Program Discovery Module
try:
    from modules.discovery import ProgramLoader, ProgramScorer, TargetSelector
    DISCOVERY_AVAILABLE = True
except ImportError:
    DISCOVERY_AVAILABLE = False

# Knowledge artifacts (Top-50 BBP)
KNOWLEDGE_DIR = ROOT / 'artifacts' / 'knowledge'
CANON_JSONL = KNOWLEDGE_DIR / 'bbp_programs_top50_canonical.jsonl'
CANON_CSV = KNOWLEDGE_DIR / 'bbp_priority_rank_top50_canonical.csv'
VALIDATION_JSON = KNOWLEDGE_DIR / 'bbp_top50_url_validation.json'
FALLBACK_JSONL = KNOWLEDGE_DIR / 'bbp_programs_top50.jsonl'
FALLBACK_CSV = KNOWLEDGE_DIR / 'bbp_priority_rank_top50.csv'
MD_SUMMARY = KNOWLEDGE_DIR / 'BBP_TOP50.md'

# Initialize discovery components if available
_loader = None
_scorer = None
_selector = None

def _get_discovery_components():
    global _loader, _scorer, _selector
    if DISCOVERY_AVAILABLE and _loader is None:
        _loader = ProgramLoader(KNOWLEDGE_DIR)
        _scorer = ProgramScorer()
        _selector = TargetSelector()
    return _loader, _scorer, _selector

def _read_jsonl(path: Path):
    items = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                import json
                items.append(json.loads(line))
    except FileNotFoundError:
        return []
    return items

@router.get('/bbp/top50')
async def bbp_top50(n: int = 50) -> Dict[str, Any]:
    data = _read_jsonl(CANON_JSONL) or _read_jsonl(FALLBACK_JSONL)
    if not data:
        return {'programs': [], 'count': 0, 'source': None}
    data.sort(key=lambda r: r.get('priority_score', 0.0), reverse=True)
    sel = data[: max(1, min(int(n), 50))]
    return {'programs': sel, 'count': len(sel), 'source': str(CANON_JSONL if (CANON_JSONL.exists()) else FALLBACK_JSONL)}

@router.get('/bbp/top10')
async def bbp_top10() -> Dict[str, Any]:
    return await bbp_top50(n=10)  # type: ignore

@router.get('/bbp/top50/validation')
async def bbp_top50_validation() -> Dict[str, Any]:
    import json
    if not VALIDATION_JSON.exists():
        return {'validation': [], 'available': False}
    return {'validation': json.loads(VALIDATION_JSON.read_text()), 'available': True}

@router.get('/bbp/top50/download')
async def bbp_top50_download(fmt: str = 'canonical_jsonl'):
    fmt = (fmt or '').lower()
    mapping = {
        'canonical_jsonl': (CANON_JSONL, 'text/plain'),
        'canonical_csv': (CANON_CSV, 'text/csv'),
        'jsonl': (FALLBACK_JSONL, 'text/plain'),
        'csv': (FALLBACK_CSV, 'text/csv'),
        'md': (MD_SUMMARY, 'text/markdown'),
        'validation': (VALIDATION_JSON, 'application/json'),
    }
    if fmt not in mapping:
        from fastapi import HTTPException
        raise HTTPException(400, detail='unsupported_format')
    path, media = mapping[fmt]
    if not path.exists():
        from fastapi import HTTPException
        raise HTTPException(404, detail='file_not_found')
    return FileResponse(path, media_type=media, filename=path.name)


from ..core.jobs import enqueue
from ..core.logs import log_decision


# ============================================================================
# PHASE 3: PROGRAM DISCOVERY & INTELLIGENT TARGET SELECTION
# ============================================================================

@router.get('/discovery/stats')
async def discovery_stats() -> Dict[str, Any]:
    """Get statistics on all available programs."""
    if not DISCOVERY_AVAILABLE:
        raise HTTPException(503, 'Discovery module not available')

    loader, _, _ = _get_discovery_components()
    stats = loader.get_program_stats()

    return {
        'ok': True,
        'stats': stats,
        'timestamp': time.time(),
    }


@router.get('/discovery/programs/all')
async def discovery_all_programs() -> Dict[str, Any]:
    """Get all discovered programs with metadata."""
    if not DISCOVERY_AVAILABLE:
        raise HTTPException(503, 'Discovery module not available')

    loader, _, _ = _get_discovery_components()
    programs = loader.load_programs()

    return {
        'ok': True,
        'count': len(programs),
        'programs': programs,
    }


@router.get('/discovery/programs/filter')
async def discovery_filter_programs(
    tags: Optional[str] = None,
    market: Optional[str] = None,
    priority: Optional[str] = None,
    min_payout: Optional[int] = None,
) -> Dict[str, Any]:
    """Filter programs by multiple criteria."""
    if not DISCOVERY_AVAILABLE:
        raise HTTPException(503, 'Discovery module not available')

    loader, _, _ = _get_discovery_components()

    # Parse tags if provided
    exploitability_tags = None
    if tags:
        exploitability_tags = [t.strip() for t in tags.split(',')]

    filtered = loader.filter_programs(
        exploitability_tags=exploitability_tags,
        market=market,
        priority_bucket=priority,
        min_payout=min_payout,
    )

    return {
        'ok': True,
        'query': {
            'tags': exploitability_tags,
            'market': market,
            'priority': priority,
            'min_payout': min_payout,
        },
        'count': len(filtered),
        'programs': filtered,
    }


@router.get('/discovery/programs/by-market/{market}')
async def discovery_programs_by_market(market: str) -> Dict[str, Any]:
    """Get all programs in a specific market."""
    if not DISCOVERY_AVAILABLE:
        raise HTTPException(503, 'Discovery module not available')

    loader, _, _ = _get_discovery_components()
    programs = loader.get_programs_by_market(market)

    return {
        'ok': True,
        'market': market,
        'count': len(programs),
        'programs': programs,
    }


@router.get('/discovery/programs/by-tag/{tag}')
async def discovery_programs_by_tag(tag: str) -> Dict[str, Any]:
    """Get programs that match an exploitability tag."""
    if not DISCOVERY_AVAILABLE:
        raise HTTPException(503, 'Discovery module not available')

    loader, _, _ = _get_discovery_components()
    programs = loader.get_programs_by_exploitability(tag)

    return {
        'ok': True,
        'tag': tag,
        'count': len(programs),
        'programs': programs,
    }


@router.get('/discovery/score/all')
async def discovery_score_all() -> Dict[str, Any]:
    """Score all programs for K1 targeting."""
    if not DISCOVERY_AVAILABLE:
        raise HTTPException(503, 'Discovery module not available')

    loader, scorer, _ = _get_discovery_components()
    programs = loader.load_programs()
    scored = scorer.score_programs(programs, sort=True)

    return {
        'ok': True,
        'count': len(scored),
        'scores': scored,
    }


@router.get('/discovery/score/by-objective/{objective}')
async def discovery_score_by_objective(objective: str) -> Dict[str, Any]:
    """
    Get programs ranked by specific K1 objective.

    Objectives: balanced, high_payout, high_confidence, research
    """
    if not DISCOVERY_AVAILABLE:
        raise HTTPException(503, 'Discovery module not available')

    if objective not in ['balanced', 'high_payout', 'high_confidence', 'research']:
        raise HTTPException(400, 'Invalid objective')

    loader, scorer, _ = _get_discovery_components()
    programs = loader.load_programs()
    ranked = scorer.rank_for_k1_objective(programs, objective)

    return {
        'ok': True,
        'objective': objective,
        'count': len(ranked),
        'ranked': ranked,
    }


@router.get('/discovery/recommendations/top-targets')
async def discovery_top_targets(
    count: int = 5,
    objective: str = 'balanced',
) -> Dict[str, Any]:
    """Get top recommended targets for immediate autonomous scanning."""
    if not DISCOVERY_AVAILABLE:
        raise HTTPException(503, 'Discovery module not available')

    if count < 1 or count > 50:
        raise HTTPException(400, 'count must be between 1 and 50')

    loader, scorer, _ = _get_discovery_components()
    programs = loader.load_programs()

    ranked = scorer.rank_for_k1_objective(programs, objective)
    targets = ranked[:count]

    return {
        'ok': True,
        'objective': objective,
        'recommended_count': len(targets),
        'targets': targets,
    }


@router.post('/discovery/select/single')
async def discovery_select_single(
    strategy: str = 'greedy',
) -> Dict[str, Any]:
    """
    Select a single target for autonomous scanning.

    Strategies: greedy, round_robin, random_top10, balanced
    """
    if not DISCOVERY_AVAILABLE:
        raise HTTPException(503, 'Discovery module not available')

    if strategy not in ['greedy', 'round_robin', 'random_top10', 'balanced']:
        raise HTTPException(400, 'Invalid strategy')

    loader, scorer, selector = _get_discovery_components()
    programs = loader.load_programs()
    scored = scorer.score_programs(programs, sort=True)

    selected = selector.select_target(programs, scored, strategy)

    if not selected:
        raise HTTPException(404, 'No programs available for selection')

    return {
        'ok': True,
        'strategy': strategy,
        'selected': selected,
    }


@router.post('/discovery/select/batch')
async def discovery_select_batch(
    batch_size: int = 3,
    strategy: str = 'diverse',
) -> Dict[str, Any]:
    """
    Select multiple targets for parallel scanning.

    Strategies: score_based, diverse, market_spread
    """
    if not DISCOVERY_AVAILABLE:
        raise HTTPException(503, 'Discovery module not available')

    if strategy not in ['score_based', 'diverse', 'market_spread']:
        raise HTTPException(400, 'Invalid strategy')

    if batch_size < 1 or batch_size > 20:
        raise HTTPException(400, 'batch_size must be between 1 and 20')

    loader, scorer, selector = _get_discovery_components()
    programs = loader.load_programs()
    scored = scorer.score_programs(programs, sort=True)

    selected = selector.select_batch(programs, scored, batch_size, strategy)

    return {
        'ok': True,
        'strategy': strategy,
        'batch_size': len(selected),
        'selected': selected,
    }


@router.post('/discovery/select/for-autonomy')
async def discovery_select_for_autonomy(
    autonomy_tier: int = 0,
) -> Dict[str, Any]:
    """
    Get programs suitable for a specific autonomy tier.

    Tiers:
    - 0 (PLANNING): All programs, HiL approval required
    - 1 (NOTIFICATION): Only verified, high-acceptance programs
    - 2 (APPROVAL): Only high-confidence programs
    - 3 (AUTONOMOUS): Only proven top performers
    """
    if not DISCOVERY_AVAILABLE:
        raise HTTPException(503, 'Discovery module not available')

    if autonomy_tier < 0 or autonomy_tier > 3:
        raise HTTPException(400, 'autonomy_tier must be 0-3')

    loader, scorer, selector = _get_discovery_components()
    programs = loader.load_programs()
    scored = scorer.score_programs(programs, sort=True)

    recommended = selector.recommend_for_autonomy_tier(programs, scored, autonomy_tier)

    tier_names = {
        0: 'PLANNING',
        1: 'NOTIFICATION',
        2: 'APPROVAL',
        3: 'AUTONOMOUS',
    }

    return {
        'ok': True,
        'autonomy_tier': autonomy_tier,
        'tier_name': tier_names.get(autonomy_tier),
        'recommended_count': len(recommended),
        'programs': recommended,
    }


@router.post('/discovery/select/rotation')
async def discovery_select_rotation(
    rotation_days: int = 7,
) -> Dict[str, Any]:
    """
    Select programs for rotation over N days (one per day).
    Avoids repeating recently scanned targets.
    """
    if not DISCOVERY_AVAILABLE:
        raise HTTPException(503, 'Discovery module not available')

    if rotation_days < 1 or rotation_days > 30:
        raise HTTPException(400, 'rotation_days must be between 1 and 30')

    loader, scorer, selector = _get_discovery_components()
    programs = loader.load_programs()
    scored = scorer.score_programs(programs, sort=True)

    rotation = selector.select_for_rotation(programs, scored, rotation_days)

    return {
        'ok': True,
        'rotation_days': rotation_days,
        'selected_count': len(rotation),
        'rotation': rotation,
    }


@router.get('/discovery/metrics/selection')
async def discovery_selection_metrics() -> Dict[str, Any]:
    """Get metrics on target selection history."""
    if not DISCOVERY_AVAILABLE:
        raise HTTPException(503, 'Discovery module not available')

    _, _, selector = _get_discovery_components()
    metrics = selector.get_selection_metrics()

    return {
        'ok': True,
        'metrics': metrics,
    }


@router.get('/discovery/market-distribution')
async def discovery_market_distribution() -> Dict[str, Any]:
    """Get distribution of programs across markets."""
    if not DISCOVERY_AVAILABLE:
        raise HTTPException(503, 'Discovery module not available')

    loader, _, _ = _get_discovery_components()
    distribution = loader.get_market_distribution()

    return {
        'ok': True,
        'markets': distribution,
    }


@router.get('/discovery/exploitability-coverage')
async def discovery_exploitability_coverage() -> Dict[str, Any]:
    """Get coverage of exploitability tags across programs."""
    if not DISCOVERY_AVAILABLE:
        raise HTTPException(503, 'Discovery module not available')

    loader, _, _ = _get_discovery_components()
    coverage = loader.get_exploitability_coverage()

    return {
        'ok': True,
        'tags': coverage,
    }


@router.post('/discovery/group-by-objective')
async def discovery_group_by_objective() -> Dict[str, Any]:
    """
    Get programs grouped by different K1 objectives.
    Useful for choosing scanning strategy.
    """
    if not DISCOVERY_AVAILABLE:
        raise HTTPException(503, 'Discovery module not available')

    loader, scorer, _ = _get_discovery_components()
    programs = loader.load_programs()

    grouped = scorer.group_programs_by_objective(programs)

    return {
        'ok': True,
        'objectives': list(grouped.keys()),
        'grouped': {
            obj: programs[:3]  # Top 3 per objective
            for obj, programs in grouped.items()
        },
    }


@router.post('/bbp/queue')
async def bbp_queue(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Queue a plan-mode OSINT dork run for a given target with scope acceptance flagged.
    # This performs a plan-mode run (no external calls) via /dorks/run and returns job + run info.
    target = (payload.get('target') or '').strip()
    if not target:
        raise HTTPException(400, 'target required')
    mode = (payload.get('mode') or 'plan').lower()
    chain = payload.get('chain')  # optional
    auto = bool(payload.get('auto', True))

    # DUPLICATE_PREFLIGHT: block recent identical plan runs (6h window)
    try:
        from apps.backend.src.core.run_store import load_all_runs
        import time as _t
        recent = load_all_runs() or []
        _now = _t.time()
        def _age_sec(ts: str):
            try:
                return _now - _t.mktime(_t.strptime(ts, '%Y-%m-%dT%H:%M:%SZ'))
            except Exception:
                return 10**9
        for r in recent:
            if _age_sec(r.get('timestamp','1970-01-01T00:00:00Z')) < 6*3600:
                if r.get('target') == target and (r.get('chain') or 'default_chain') == (chain or 'default_chain'):
                    from fastapi import HTTPException
                    raise HTTPException(status_code=409, detail='duplicate_plan_recent')
    except Exception:
        pass
    

    job = enqueue('dorks_scan', {
        'target': target,
        'mode': mode,
        'chain': chain,
        'accept_scope': True,
    })
    try:
        log_decision(job['id'], 'bbp_queue', {'target': target, 'mode': mode, 'chain': chain})
    except Exception:
        pass

    out: Dict[str, Any] = {'queued': True, 'job': job}

    if auto:
        # Dev convenience: directly call plan-mode /dorks/run to persist a run record (no external calls)
        try:
            from fastapi.testclient import TestClient
            from apps.backend.src.main import app as _app
            client = TestClient(_app)
            AUTH = {'Authorization': 'Bearer devtoken'}
            body = {'target': target, 'mode': 'plan', 'chain': chain}
            r = client.post('/dorks/run', headers=AUTH, json=body)
            out['auto_run'] = {'status': r.status_code, 'body': r.json()}
        except Exception as e:
            out['auto_run'] = {'status': 'error', 'error': str(e)}

    return out
