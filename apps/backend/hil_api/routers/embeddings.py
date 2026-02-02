from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
import numpy as np
from ..db import get_db
from ..security import RBAC, Permission
from ..embeddings import embed_texts

router = APIRouter(prefix="/embeddings", tags=["embeddings"])

class EmbedItem(BaseModel):
    scope: str
    ref_type: str
    ref_id: str
    text: str
    model: str | None = None

class EmbedBatch(BaseModel):
    items: List[EmbedItem]

@router.post("/index", dependencies=[Depends(RBAC(Permission.MANAGE_CONFIG))])
def index_embeddings(body: EmbedBatch, db: Session = Depends(get_db)):
    if not body.items:
        return {"inserted": 0}
    texts = [it.text for it in body.items]
    vecs = embed_texts(texts)
    if vecs.shape[1] != 768:
        raise HTTPException(500, f"Vector dim must be 768; got {vecs.shape[1]}")
    conn = db.connection()
    inserted = 0
    for it, v in zip(body.items, vecs):
        vstr = '[' + ','.join(str(float(x)) for x in v.tolist()) + ']'
        sql = text("""
            INSERT INTO embeddings (scope, ref_type, ref_id, model, dim, vec, meta)
            VALUES (:scope, :ref_type, :ref_id, :model, :dim, :vec::vector, '{}'::jsonb)
            ON CONFLICT DO NOTHING
        """)
        conn.execute(sql, {
            'scope': it.scope,
            'ref_type': it.ref_type,
            'ref_id': it.ref_id,
            'model': it.model or 'auto',
            'dim': 768,
            'vec': vstr,
        })
        inserted += 1
    return {"inserted": inserted}

@router.get("/search")
def search_embeddings(query: str, scope: str = Query('finding'), top_k: int = Query(10, ge=1, le=100), db: Session = Depends(get_db)) -> Dict[str, Any]:
    vec = embed_texts([query])[0]
    vstr = '[' + ','.join(str(float(x)) for x in vec.tolist()) + ']'
    sql = text("""
        SELECT ref_type, ref_id, 1 - (1 - (vec <-> :vec::vector)) AS score
        FROM embeddings
        WHERE scope = :scope
        ORDER BY vec <-> :vec::vector
        LIMIT :k
    """)
    rows = db.connection().execute(sql, {'vec': vstr, 'scope': scope, 'k': top_k}).fetchall()
    results = [{"ref_type": r[0], "ref_id": r[1], "distance": float(r[2])} for r in rows]
    return {"count": len(results), "results": results}
