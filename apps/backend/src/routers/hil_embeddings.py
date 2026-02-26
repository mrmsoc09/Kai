from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.hil_db import get_db
from ..core.hil_embeddings import embed_texts
from ..core.hil_security import Permission, RBAC


router = APIRouter(prefix="/embeddings", tags=["hil-embeddings"])


class EmbedItem(BaseModel):
    scope: str
    ref_type: str
    ref_id: str
    text: str
    model: Optional[str] = None


class EmbedBatch(BaseModel):
    items: List[EmbedItem]


@router.post("/index", dependencies=[Depends(RBAC(Permission.MANAGE_CONFIG))])
async def index_embeddings(body: EmbedBatch, db: AsyncSession = Depends(get_db)):
    if not body.items:
        return {"inserted": 0}

    texts = [item.text for item in body.items]
    vectors = await asyncio.to_thread(embed_texts, texts)
    if vectors.shape[1] != 768:
        raise HTTPException(500, f"Vector dim must be 768; got {vectors.shape[1]}")

    inserted = 0
    stmt = text(
        """
        INSERT INTO embeddings (scope, ref_type, ref_id, model, dim, vec, meta)
        VALUES (:scope, :ref_type, :ref_id, :model, :dim, :vec::vector, '{}'::jsonb)
        ON CONFLICT DO NOTHING
        """
    )
    for item, vector in zip(body.items, vectors):
        vector_str = "[" + ",".join(str(float(x)) for x in vector.tolist()) + "]"
        await db.execute(
            stmt,
            {
                "scope": item.scope,
                "ref_type": item.ref_type,
                "ref_id": item.ref_id,
                "model": item.model or "auto",
                "dim": 768,
                "vec": vector_str,
            },
        )
        inserted += 1

    return {"inserted": inserted}


@router.get("/search")
async def search_embeddings(
    query: str,
    scope: str = Query("finding"),
    top_k: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    vector = (await asyncio.to_thread(embed_texts, [query]))[0]
    vector_str = "[" + ",".join(str(float(x)) for x in vector.tolist()) + "]"

    stmt = text(
        """
        SELECT ref_type, ref_id, 1 - (1 - (vec <-> :vec::vector)) AS score
        FROM embeddings
        WHERE scope = :scope
        ORDER BY vec <-> :vec::vector
        LIMIT :k
        """
    )
    result = await db.execute(stmt, {"vec": vector_str, "scope": scope, "k": top_k})
    rows = result.fetchall()
    results = [
        {"ref_type": row[0], "ref_id": row[1], "distance": float(row[2])}
        for row in rows
    ]
    return {"count": len(results), "results": results}
