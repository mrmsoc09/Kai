import os, json, time, hashlib, urllib.parse, urllib.request, pathlib
from typing import List, Dict, Any, Optional

ROOT = pathlib.Path(__file__).resolve().parents[3]
CACHE_DIR = ROOT / ".cache" / "google_cse"
ART_DIR = ROOT / "artifacts" / "dork_runs"
CACHE_TTL_SECS = 6 * 60 * 60  # 6 hours

class GoogleCSE:
    def __init__(self, api_key: Optional[str]=None, cse_id: Optional[str]=None):
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        self.cse_id  = cse_id  or os.environ.get("GOOGLE_CSE_ID", "")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        ART_DIR.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, q: str, num: int) -> pathlib.Path:
        h = hashlib.sha256(f"{q}\n{num}".encode()).hexdigest()
        return CACHE_DIR / f"{h}.json"

    def _load_cache(self, path: pathlib.Path) -> Optional[Dict[str, Any]]:
        if not path.exists():
            return None
        if time.time() - path.stat().st_mtime > CACHE_TTL_SECS:
            return None
        try:
            return json.loads(path.read_text())
        except Exception:
            return None

    def _save_cache(self, path: pathlib.Path, data: Dict[str, Any]) -> None:
        try:
            path.write_text(json.dumps(data, ensure_ascii=False))
        except Exception:
            pass

    def search(self, query: str, num: int = 5) -> Dict[str, Any]:
        if not self.api_key or not self.cse_id:
            return {"error": "Missing GOOGLE_API_KEY or GOOGLE_CSE_ID"}
        q = query.strip()
        if not q:
            return {"error": "Empty query"}
        cp = self._cache_path(q, num)
        cached = self._load_cache(cp)
        if cached:
            return {"cached": True, **cached}
        params = {
            "key": self.api_key,
            "cx": self.cse_id,
            "q": q,
            "num": str(max(1, min(num, 10)))
        }
        url = "https://www.googleapis.com/customsearch/v1?" + urllib.parse.urlencode(params)
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                raw = resp.read()
            data = json.loads(raw.decode("utf-8", "ignore"))
        except Exception as e:
            return {"error": f"request_failed: {e}"}
        items = []
        for it in data.get("items", [])[:num]:
            items.append({
                "title": it.get("title"),
                "link": it.get("link"),
                "snippet": it.get("snippet"),
                "cacheId": it.get("cacheId"),
                "displayLink": it.get("displayLink"),
            })
        out = {"query": q, "count": len(items), "items": items}
        self._save_cache(cp, out)
        return out

    def audit_log(self, run_id: str, planned: List[str], executed: List[Dict[str, Any]], meta: Dict[str, Any]) -> str:
        ts = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        run_dir = ART_DIR / f"{ts}-{run_id}"
        run_dir.mkdir(parents=True, exist_ok=True)
        bundle = {
            "run_id": run_id,
            "timestamp": ts,
            "planned_queries": planned,
            "executed_results": executed,
            "meta": meta,
        }
        path = run_dir / "audit.json"
        path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2))
        return str(path)
