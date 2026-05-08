from __future__ import annotations
from typing import Dict, Any, List, Optional
import os
import logging
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue

logger = logging.getLogger(__name__)

class QdrantVectorStore:
    def __init__(self, url: str, api_key: Optional[str] = None, collection_name: str = "k1_collection"):
        self.client = QdrantClient(url=url, api_key=api_key)
        self.collection_name = collection_name
        self.available = False
        try:
            self.client.get_collection(collection_name=self.collection_name)
            self.available = True
            logger.info(f"Connected to existing Qdrant collection: {self.collection_name}")
        except Exception as e:
            logger.warning(f"Qdrant collection {self.collection_name} not found, attempting to create. Error: {e}")
            try:
                # Assuming a default vector size for now. This should be configurable.
                # A common embedding model output size is 1536 (e.g., OpenAI ada-002)
                # or 768 (e.g., MiniLM-L6-v2). Let's use 768 as a reasonable default.
                # This will need to be matched with the embedding model used by the application.
                self.client.recreate_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=768, distance=Distance.COSINE),
                )
                self.available = True
                logger.info(f"Created new Qdrant collection: {self.collection_name}")
            except Exception as create_e:
                logger.error(f"Failed to connect or create Qdrant collection {self.collection_name}: {create_e}")
                self.available = False

    def upsert(self, items: List[Dict[str, Any]]) -> int:
        if not self.available:
            logger.warning("Qdrant client not available, skipping upsert.")
            return 0

        points = []
        for item in items:
            _id = str(item.get("id"))
            vector = item.get("vector")
            metadata = item.get("meta") or {}
            text = item.get("text")
            if text:
                metadata["text"] = text # Store text in metadata for retrieval

            if _id and vector is not None:
                points.append(PointStruct(id=_id, vector=vector, payload=metadata))
            else:
                logger.warning(f"Skipping Qdrant upsert for item due to missing id or vector: {item}")

        if points:
            try:
                self.client.upsert(
                    collection_name=self.collection_name,
                    wait=True,
                    points=points
                )
                logger.debug(f"Upserted {len(points)} items to Qdrant collection {self.collection_name}")
                return len(points)
            except Exception as e:
                logger.error(f"Failed to upsert items to Qdrant collection {self.collection_name}: {e}")
                return 0
        return 0

    def search(self, query_vector: List[float], top_k: int = 5, min_score: float = 0.2, filter_payload: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not self.available:
            logger.warning("Qdrant client not available, skipping search.")
            return []

        qdrant_filter = None
        if filter_payload:
            must_conditions = []
            for key, value in filter_payload.items():
                must_conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
            qdrant_filter = Filter(must=must_conditions)

        try:
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=qdrant_filter,
                limit=top_k,
                score_threshold=min_score,
                with_payload=True,
                with_vectors=False,
            )
            results = []
            for hit in search_result:
                result = {
                    "id": hit.id,
                    "score": hit.score,
                    "text": hit.payload.get("text"), # Assuming text is stored in payload
                    "meta": {k: v for k, v in hit.payload.items() if k != "text"}
                }
                results.append(result)
            logger.debug(f"Qdrant search returned {len(results)} results.")
            return results
        except Exception as e:
            logger.error(f"Failed to search Qdrant collection {self.collection_name}: {e}")
            return []

    def info(self) -> Dict[str, Any]:
        if not self.available:
            return {"backend": "qdrant", "available": False, "collection": self.collection_name}
        try:
            collection_info = self.client.get_collection(collection_name=self.collection_name)
            return {
                "backend": "qdrant",
                "available": True,
                "collection": self.collection_name,
                "vector_count": collection_info.vectors_count,
                "indexed_vectors_count": collection_info.indexed_vectors_count,
                "status": str(collection_info.status),
            }
        except Exception as e:
            logger.error(f"Failed to get Qdrant collection info: {e}")
            return {"backend": "qdrant", "available": False, "collection": self.collection_name, "error": str(e)}

