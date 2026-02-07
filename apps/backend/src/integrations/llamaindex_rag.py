"""
Kaison K1 - LlamaIndex RAG System
Document indexing, semantic search, and context-aware AI for vulnerability intelligence
"""

import os
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from llama_index.core import (
    VectorStoreIndex,
    Document,
    StorageContext,
    Settings,
    load_index_from_storage
)
from llama_index.core.schema import TextNode
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
import chromadb

logger = logging.getLogger(__name__)


@dataclass
class QueryResponse:
    """RAG query response"""
    query: str
    answer: str
    source_documents: List[Dict[str, Any]]
    relevance_scores: List[float]
    query_time: float


@dataclass
class IndexStats:
    """RAG index statistics"""
    total_documents: int
    total_nodes: int
    storage_size_mb: float
    last_updated: datetime


class LlamaIndexRAG:
    """RAG system for vulnerability intelligence and finding analysis"""

    def __init__(
        self,
        persist_dir: str = "var/lib/kai/rag/chroma",
        ollama_model: str = "llama3:8b",
        ollama_base_url: str = "http://localhost:11434",
        embedding_model: str = "BAAI/bge-small-en-v1.5"
    ):
        self.persist_dir = os.path.join(os.getcwd(), persist_dir)
        self.ollama_model = ollama_model
        self.ollama_base_url = ollama_base_url
        self.embedding_model_name = embedding_model

        self.index: Optional[VectorStoreIndex] = None
        self.query_engine = None
        self.vector_store = None
        self.chroma_client = None

        # Create persist directory
        os.makedirs(self.persist_dir, exist_ok=True)

        logger.info(f"Initializing LlamaIndex RAG with Ollama model: {ollama_model}")

    async def initialize(self):
        """Initialize RAG system"""
        try:
            # Configure LlamaIndex settings
            logger.info("Configuring LlamaIndex settings...")

            # Set up Ollama LLM
            Settings.llm = Ollama(
                model=self.ollama_model,
                base_url=self.ollama_base_url,
                request_timeout=120.0
            )

            # Set up embedding model
            Settings.embed_model = HuggingFaceEmbedding(
                model_name=self.embedding_model_name
            )

            # Set chunk size for documents
            Settings.chunk_size = 512
            Settings.chunk_overlap = 50

            # Initialize ChromaDB
            logger.info("Initializing ChromaDB vector store...")
            self.chroma_client = chromadb.PersistentClient(path=self.persist_dir)

            # Get or create collection
            collection = self.chroma_client.get_or_create_collection(
                name="kaison_k1_intelligence"
            )

            # Create vector store
            self.vector_store = ChromaVectorStore(chroma_collection=collection)

            # Try to load existing index
            try:
                storage_context = StorageContext.from_defaults(
                    vector_store=self.vector_store,
                    persist_dir=self.persist_dir
                )
                self.index = load_index_from_storage(storage_context)
                logger.info("Loaded existing RAG index from storage")
            except Exception as e:
                logger.info(f"No existing index found, creating new one: {e}")
                storage_context = StorageContext.from_defaults(
                    vector_store=self.vector_store
                )
                self.index = VectorStoreIndex(
                    nodes=[],
                    storage_context=storage_context
                )

            # Create query engine
            self.query_engine = self.index.as_query_engine(
                similarity_top_k=5,
                response_mode="compact"
            )

            logger.info("LlamaIndex RAG system initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize RAG system: {e}")
            raise

    async def index_documents(self, documents: List[Document]) -> int:
        """Index documents into the RAG system"""
        if not self.index:
            raise RuntimeError("RAG system not initialized")

        try:
            logger.info(f"Indexing {len(documents)} documents...")

            # Add documents to index
            for doc in documents:
                self.index.insert(doc)

            # Persist index
            self.index.storage_context.persist(persist_dir=self.persist_dir)

            logger.info(f"Successfully indexed {len(documents)} documents")
            return len(documents)

        except Exception as e:
            logger.error(f"Error indexing documents: {e}")
            raise

    async def index_rss_items(self, rss_items: List[Dict[str, Any]]) -> int:
        """Index RSS feed items for RAG"""
        documents = []

        for item in rss_items:
            try:
                # Create document text
                text = f"""
Title: {item.get('title', '')}
Published: {item.get('published', '')}
Source: {item.get('feed', '')}
CVEs: {', '.join(item.get('cves', []))}

Content:
{item.get('content', item.get('summary', ''))}
"""

                # Create metadata
                metadata = {
                    'source': 'rss_feed',
                    'feed': item.get('feed', ''),
                    'title': item.get('title', ''),
                    'published': str(item.get('published', '')),
                    'link': item.get('link', ''),
                    'cves': ','.join(item.get('cves', [])),
                    'indexed_at': datetime.now().isoformat()
                }

                # Create document
                doc = Document(
                    text=text,
                    metadata=metadata
                )
                documents.append(doc)

            except Exception as e:
                logger.error(f"Error creating document from RSS item: {e}")
                continue

        # Index all documents
        if documents:
            return await self.index_documents(documents)
        else:
            return 0

    async def index_finding(self, finding_data: Dict[str, Any]) -> bool:
        """Index a security finding for RAG"""
        try:
            # Create document text
            text = f"""
Finding ID: {finding_data.get('id', '')}
Target: {finding_data.get('target', '')}
Severity: {finding_data.get('severity', '')}
CVSS Score: {finding_data.get('cvss', 0)}
Type: {finding_data.get('vulnerability_type', '')}
Tool: {finding_data.get('tool', '')}

Description:
{finding_data.get('description', '')}

Technical Details:
{finding_data.get('technical_details', '')}

Validation Status: {finding_data.get('validation_status', 'pending')}
"""

            # Create metadata
            metadata = {
                'source': 'finding',
                'finding_id': finding_data.get('id', ''),
                'target': finding_data.get('target', ''),
                'severity': finding_data.get('severity', ''),
                'cvss': finding_data.get('cvss', 0),
                'vulnerability_type': finding_data.get('vulnerability_type', ''),
                'validation_status': finding_data.get('validation_status', 'pending'),
                'indexed_at': datetime.now().isoformat()
            }

            # Create and index document
            doc = Document(text=text, metadata=metadata)
            await self.index_documents([doc])

            logger.info(f"Indexed finding: {finding_data.get('id', 'unknown')}")
            return True

        except Exception as e:
            logger.error(f"Error indexing finding: {e}")
            return False

    async def query(self, query_str: str, top_k: int = 5) -> QueryResponse:
        """Semantic search over indexed documents"""
        if not self.query_engine:
            raise RuntimeError("RAG system not initialized")

        try:
            import time
            start_time = time.time()

            logger.info(f"Querying RAG: {query_str}")

            # Configure retriever with top_k
            retriever = VectorIndexRetriever(
                index=self.index,
                similarity_top_k=top_k
            )

            # Create query engine with retriever
            query_engine = RetrieverQueryEngine(retriever=retriever)

            # Execute query
            response = query_engine.query(query_str)

            query_time = time.time() - start_time

            # Extract source documents
            source_documents = []
            relevance_scores = []

            if hasattr(response, 'source_nodes'):
                for node in response.source_nodes:
                    source_documents.append({
                        'text': node.node.text[:500] + '...' if len(node.node.text) > 500 else node.node.text,
                        'metadata': node.node.metadata,
                        'score': node.score
                    })
                    relevance_scores.append(node.score)

            logger.info(f"Query completed in {query_time:.2f}s with {len(source_documents)} results")

            return QueryResponse(
                query=query_str,
                answer=str(response),
                source_documents=source_documents,
                relevance_scores=relevance_scores,
                query_time=query_time
            )

        except Exception as e:
            logger.error(f"Error executing query: {e}")
            raise

    async def analyze_finding_context(self, finding_id: str) -> str:
        """Get contextual analysis of a finding using RAG"""
        try:
            # Query for similar findings
            query = f"Similar security findings and context for finding {finding_id}"
            response = await self.query(query, top_k=5)

            # Build context
            context = f"# Contextual Analysis for Finding {finding_id}\n\n"
            context += f"## AI Analysis\n{response.answer}\n\n"

            if response.source_documents:
                context += "## Related Findings and Intelligence\n"
                for i, doc in enumerate(response.source_documents, 1):
                    context += f"\n### Source {i} (Relevance: {doc['score']:.2f})\n"
                    context += f"{doc['text']}\n"

            return context

        except Exception as e:
            logger.error(f"Error analyzing finding context: {e}")
            return f"Error analyzing finding context: {str(e)}"

    async def enrich_agent_zero_context(self, user_query: str) -> str:
        """Provide RAG context for Agent Zero responses"""
        try:
            # Query RAG for relevant context
            response = await self.query(user_query, top_k=3)

            # Build context string
            context = "# Relevant Security Intelligence\n\n"

            if response.source_documents:
                for i, doc in enumerate(response.source_documents, 1):
                    metadata = doc.get('metadata', {})
                    source_type = metadata.get('source', 'unknown')

                    context += f"## Context Source {i} (Relevance: {doc['score']:.2f})\n"
                    context += f"**Source Type:** {source_type}\n"

                    if source_type == 'rss_feed':
                        context += f"**Feed:** {metadata.get('feed', 'N/A')}\n"
                        context += f"**CVEs:** {metadata.get('cves', 'N/A')}\n"
                    elif source_type == 'finding':
                        context += f"**Finding ID:** {metadata.get('finding_id', 'N/A')}\n"
                        context += f"**Severity:** {metadata.get('severity', 'N/A')}\n"

                    context += f"\n{doc['text']}\n\n"
            else:
                context = "No relevant context found in RAG index."

            return context

        except Exception as e:
            logger.error(f"Error enriching Agent Zero context: {e}")
            return "RAG context unavailable."

    async def search_cves(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Semantic search for CVEs"""
        try:
            response = await self.query(query, top_k=top_k)

            results = []
            for doc in response.source_documents:
                metadata = doc.get('metadata', {})
                cves_str = metadata.get('cves', '')

                if cves_str:
                    cves = cves_str.split(',')
                    results.append({
                        'cves': cves,
                        'title': metadata.get('title', ''),
                        'source': metadata.get('feed', metadata.get('source', '')),
                        'relevance': doc['score'],
                        'text': doc['text']
                    })

            return results

        except Exception as e:
            logger.error(f"Error searching CVEs: {e}")
            return []

    async def generate_nuclei_template(self, cve_id: str) -> Optional[str]:
        """Generate Nuclei template for a CVE using RAG context"""
        try:
            # Query for CVE details
            query = f"Technical exploitation details and vulnerability information for {cve_id}"
            response = await self.query(query, top_k=3)

            if not response.source_documents:
                logger.warning(f"No context found for {cve_id}")
                return None

            # Build context for template generation
            context = f"CVE: {cve_id}\n\n"
            context += "Context from security intelligence:\n"
            for doc in response.source_documents:
                context += f"\n{doc['text']}\n"

            # Generate template using Ollama
            prompt = f"""Generate a Nuclei template for the following vulnerability.
Include id, info section with severity, description, and detection logic.

{context}

Generate a complete Nuclei YAML template:"""

            # Use Ollama directly
            llm = Settings.llm
            template_response = await llm.acomplete(prompt)

            logger.info(f"Generated Nuclei template for {cve_id}")
            return str(template_response)

        except Exception as e:
            logger.error(f"Error generating Nuclei template: {e}")
            return None

    async def get_stats(self) -> IndexStats:
        """Get RAG index statistics"""
        try:
            # Get storage size
            import shutil
            storage_size = 0
            if os.path.exists(self.persist_dir):
                storage_size = shutil.disk_usage(self.persist_dir).used / (1024 * 1024)

            # Get document count from ChromaDB
            total_documents = 0
            if self.chroma_client:
                try:
                    collection = self.chroma_client.get_collection("kaison_k1_intelligence")
                    total_documents = collection.count()
                except Exception as e:
                    logger.warning(f"Could not get document count: {e}")

            return IndexStats(
                total_documents=total_documents,
                total_nodes=total_documents,  # Approximate
                storage_size_mb=storage_size,
                last_updated=datetime.now()
            )

        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            return IndexStats(
                total_documents=0,
                total_nodes=0,
                storage_size_mb=0,
                last_updated=datetime.now()
            )

    async def clear_index(self):
        """Clear all documents from index"""
        try:
            logger.warning("Clearing RAG index...")

            if self.chroma_client:
                # Delete collection
                self.chroma_client.delete_collection("kaison_k1_intelligence")

                # Recreate collection
                collection = self.chroma_client.create_collection("kaison_k1_intelligence")
                self.vector_store = ChromaVectorStore(chroma_collection=collection)

                # Recreate index
                storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
                self.index = VectorStoreIndex(nodes=[], storage_context=storage_context)
                self.query_engine = self.index.as_query_engine(similarity_top_k=5)

            logger.info("RAG index cleared successfully")

        except Exception as e:
            logger.error(f"Error clearing index: {e}")
            raise


# Singleton pattern
_rag_instance: Optional[LlamaIndexRAG] = None


async def get_llamaindex_rag() -> LlamaIndexRAG:
    """Get or create RAG instance"""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = LlamaIndexRAG()
        await _rag_instance.initialize()
    return _rag_instance


async def initialize_rag():
    """Initialize RAG system on startup"""
    await get_llamaindex_rag()
