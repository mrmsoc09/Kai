from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple
import json, difflib, re

ROOT = Path(__file__).resolve().parents[4]
REPORTS = ROOT / 'artifacts' / 'reports'

# Optional embeddings
try:
    from core.embeddings import search_similar  # type: ignore
    _EMB = True
except Exception:
    _EMB = False


def _title_from_report_md(p: Path) -> str | None:
    try:
        txt = p.read_text(errors='ignore')
        # First H1 line
        m = re.search(r'^#\s*(.+)$', txt, re.MULTILINE)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return None


def _collect_existing_titles() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not REPORTS.exists():
        return out
    for run_dir in sorted([p for p in REPORTS.iterdir() if p.is_dir()]):
        title = None
        meta = run_dir / 'meta.json'
        if meta.exists():
            try:
                mj = json.loads(meta.read_text())
                title = (mj.get('finding') or {}).get('title') or mj.get('title')
            except Exception:
                pass
        if not title:
            md = run_dir / 'report.md'
            if md.exists():
                title = _title_from_report_md(md)
        if title:
            out.append({'run_id': run_dir.name, 'title': title})
    return out


def check_title_duplicate(title: str, threshold: float = 0.85) -> Dict[str, Any]:
    """Legacy title-based duplicate check using difflib only."""
    existing = _collect_existing_titles()
    matches: List[Dict[str, Any]] = []
    for e in existing:
        sim = difflib.SequenceMatcher(a=title.lower(), b=e['title'].lower()).ratio()
        if sim >= threshold:
            matches.append({'run_id': e['run_id'], 'title': e['title'], 'similarity': round(sim, 3)})
    status = 'duplicate_suspected' if matches else 'clear'
    return {'status': status, 'matches': matches, 'count': len(matches), 'threshold': threshold}


def vector_duplicate(title: str, summary: str | None = None, threshold: float = 0.8) -> Dict[str, Any]:
    """Embedding-first duplicate check; falls back to difflib if embeddings unavailable.
    threshold applies to difflib; for embeddings we use a slightly lower min_score to be recall-friendly.
    """
    text = (title or '').strip()
    if summary:
        text = f"{text}\n{summary.strip()}"

    matches: List[Dict[str, Any]] = []

    # Embedding search
    if _EMB and text:
        try:
            sr = search_similar(text, top_k=5, min_score=max(0.6, threshold - 0.2))
            for em in (sr.get('matches') or []):
                matches.append({
                    'run_id': em.get('run_id'),
                    'title': em.get('text'),
                    'similarity': float(em.get('score') or 0.0)
                })
        except Exception:
            pass

    # Add difflib over local titles for robustness
    existing = _collect_existing_titles()
    for e in existing:
        sim = difflib.SequenceMatcher(a=(title or '').lower(), b=e['title'].lower()).ratio()
        if sim >= threshold:
            matches.append({'run_id': e['run_id'], 'title': e['title'], 'similarity': round(sim, 3)})

    # Deduplicate by (run_id,title) keeping highest similarity
    dedup: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for m in matches:
        key = (str(m.get('run_id')), str(m.get('title')))
        if key not in dedup or float(m.get('similarity') or 0) > float(dedup[key].get('similarity') or 0):
            dedup[key] = m
    final = list(dedup.values())
    final.sort(key=lambda x: x.get('similarity', 0.0), reverse=True)

    status = 'duplicate_suspected' if final else 'clear'
    return {'status': status, 'matches': final, 'count': len(final), 'threshold': threshold}
