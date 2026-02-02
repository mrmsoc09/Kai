"""
Embeddings Client and Vector Management
Supports OpenAI embeddings with local fallback
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from abc import ABC, abstractmethod
from enum import Enum

logger = logging.getLogger(__name__)


class EmbeddingModel(Enum):
    """Supported embedding models"""
    OPENAI_LARGE = "text-embedding-3-large"
    OPENAI_SMALL = "text-embedding-3-small"
    LOCAL_SENTENCE_TRANSFORMERS = "all-MiniLM-L6-v2"


class BaseEmbeddingClient(ABC):
    """Abstract base class for embedding clients"""

    def __init__(self, model: EmbeddingModel):
        self.model = model
        self.model_name = model.value
        self.dimension = self._get_dimension()

    @abstractmethod
    def _get_dimension(self) -> int:
        """Get embedding dimension for this model"""
        pass

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Embed a single text string"""
        pass

    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple text strings"""
        pass

    @abstractmethod
    def embed_query(self, query: str) -> List[float]:
        """Embed a query (may use different processing than text)"""
        pass


class OpenAIEmbeddingClient(BaseEmbeddingClient):
    """OpenAI Embeddings API client"""

    def __init__(self, api_key: Optional[str] = None, model: EmbeddingModel = EmbeddingModel.OPENAI_LARGE):
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not provided")

        super().__init__(model)

        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
        except ImportError:
            raise ImportError("openai package required. Install: pip install openai")

    def _get_dimension(self) -> int:
        """OpenAI embedding dimension"""
        if self.model == EmbeddingModel.OPENAI_LARGE:
            return 3072
        elif self.model == EmbeddingModel.OPENAI_SMALL:
            return 1536
        return 1536

    def embed_text(self, text: str) -> List[float]:
        """Embed a single text"""
        result = self.client.embeddings.create(
            input=text,
            model=self.model_name,
        )
        return result.data[0].embedding

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts"""
        if not texts:
            return []

        result = self.client.embeddings.create(
            input=texts,
            model=self.model_name,
        )

        embeddings = sorted(result.data, key=lambda x: x.index)
        return [e.embedding for e in embeddings]

    def embed_query(self, query: str) -> List[float]:
        """Embed a query"""
        return self.embed_text(query)


class LocalEmbeddingClient(BaseEmbeddingClient):
    """Local Sentence-Transformers embedding client"""

    def __init__(self, model: EmbeddingModel = EmbeddingModel.LOCAL_SENTENCE_TRANSFORMERS):
        super().__init__(model)

        try:
            from sentence_transformers import SentenceTransformer
            self.model_instance = SentenceTransformer(self.model_name)
        except ImportError:
            raise ImportError("sentence-transformers package required. Install: pip install sentence-transformers")

    def _get_dimension(self) -> int:
        """Get embedding dimension from model"""
        if self.model_instance:
            return self.model_instance.get_sentence_embedding_dimension()
        return 384

    def embed_text(self, text: str) -> List[float]:
        """Embed a single text"""
        embedding = self.model_instance.encode(text, convert_to_tensor=False)
        return embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts"""
        if not texts:
            return []

        embeddings = self.model_instance.encode(texts, convert_to_tensor=False)
        return [e.tolist() if hasattr(e, 'tolist') else list(e) for e in embeddings]

    def embed_query(self, query: str) -> List[float]:
        """Embed a query"""
        return self.embed_text(query)


class HybridEmbeddingClient:
    """Hybrid client with OpenAI primary and local fallback"""

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        primary_model: EmbeddingModel = EmbeddingModel.OPENAI_LARGE,
        fallback_model: EmbeddingModel = EmbeddingModel.LOCAL_SENTENCE_TRANSFORMERS,
    ):
        self.primary_client = None
        self.fallback_client = None

        if openai_api_key or os.getenv("OPENAI_API_KEY"):
            try:
                self.primary_client = OpenAIEmbeddingClient(api_key=openai_api_key, model=primary_model)
                logger.info("OpenAI embedding client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client: {str(e)}")

        try:
            self.fallback_client = LocalEmbeddingClient(model=fallback_model)
            logger.info("Local embedding client initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize local client: {str(e)}")

        if not self.primary_client and not self.fallback_client:
            raise ValueError("No embedding clients could be initialized")

        self.dimension = (self.primary_client or self.fallback_client).dimension

    def embed_text(self, text: str) -> Tuple[List[float], str]:
        """Embed text, returns (embedding, source)"""
        if self.primary_client:
            try:
                embedding = self.primary_client.embed_text(text)
                return embedding, "openai"
            except Exception as e:
                logger.warning(f"OpenAI embedding failed: {str(e)}, using fallback")

        if self.fallback_client:
            try:
                embedding = self.fallback_client.embed_text(text)
                return embedding, "local"
            except Exception as e:
                logger.error(f"Fallback embedding failed: {str(e)}")
                raise

        raise RuntimeError("No embedding clients available")

    def embed_texts(self, texts: List[str]) -> Tuple[List[List[float]], str]:
        """Embed multiple texts, returns (embeddings, source)"""
        if self.primary_client:
            try:
                embeddings = self.primary_client.embed_texts(texts)
                return embeddings, "openai"
            except Exception as e:
                logger.warning(f"OpenAI embedding failed: {str(e)}, using fallback")

        if self.fallback_client:
            try:
                embeddings = self.fallback_client.embed_texts(texts)
                return embeddings, "local"
            except Exception as e:
                logger.error(f"Fallback embedding failed: {str(e)}")
                raise

        raise RuntimeError("No embedding clients available")

    def embed_query(self, query: str) -> Tuple[List[float], str]:
        """Embed a query"""
        return self.embed_text(query)


class VectorStore:
    """In-memory vector store for development"""

    def __init__(self, embedding_client: HybridEmbeddingClient):
        self.client = embedding_client
        self.vectors: Dict[str, Dict[str, Any]] = {}
        self.metadata_index: Dict[str, List[str]] = {}

    def add_document(self, doc_id: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a document to the vector store"""
        embedding, source = self.client.embed_text(text)

        self.vectors[doc_id] = {
            "text": text,
            "embedding": embedding,
            "embedding_source": source,
            "metadata": metadata or {},
        }

        if metadata:
            for key, value in metadata.items():
                meta_key = f"{key}:{value}"
                if meta_key not in self.metadata_index:
                    self.metadata_index[meta_key] = []
                self.metadata_index[meta_key].append(doc_id)

        logger.info(f"Added document to vector store: {doc_id}")

    def add_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Add multiple documents"""
        texts = [doc["text"] for doc in documents]
        embeddings, source = self.client.embed_texts(texts)

        for i, doc in enumerate(documents):
            doc_id = doc["id"]
            self.vectors[doc_id] = {
                "text": doc["text"],
                "embedding": embeddings[i],
                "embedding_source": source,
                "metadata": doc.get("metadata", {}),
            }

            for key, value in doc.get("metadata", {}).items():
                meta_key = f"{key}:{value}"
                if meta_key not in self.metadata_index:
                    self.metadata_index[meta_key] = []
                self.metadata_index[meta_key].append(doc_id)

        logger.info(f"Added {len(documents)} documents to vector store")

    def search(self, query: str, top_k: int = 5, metadata_filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search for similar documents"""
        query_embedding, _ = self.client.embed_query(query)

        results = []
        for doc_id, doc_data in self.vectors.items():
            if metadata_filter:
                doc_metadata = doc_data.get("metadata", {})
                filter_match = all(
                    doc_metadata.get(k) == v for k, v in metadata_filter.items()
                )
                if not filter_match:
                    continue

            similarity = self._cosine_similarity(query_embedding, doc_data["embedding"])
            results.append({
                "id": doc_id,
                "text": doc_data["text"],
                "similarity": similarity,
                "metadata": doc_data.get("metadata", {}),
            })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics"""
        return {
            "total_documents": len(self.vectors),
            "embedding_dimension": self.client.dimension,
            "metadata_indexes": len(self.metadata_index),
        }

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity"""
        if not vec1 or not vec2:
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a ** 2 for a in vec1) ** 0.5
        norm2 = sum(b ** 2 for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)
