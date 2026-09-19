from __future__ import annotations

from typing import Any, Callable

from .chunking import _dot
from .embeddings import _mock_embed
from .models import Document


class EmbeddingStore:
    """
    A vector store for text chunks.

    Tries to use ChromaDB if available; falls back to an in-memory store.
    The embedding_fn parameter allows injection of mock embeddings for tests.
    """

    def __init__(
        self,
        collection_name: str = "documents",
        embedding_fn: Callable[[str], list[float]] | None = None,
    ) -> None:
        self._embedding_fn = embedding_fn or _mock_embed
        self._collection_name = collection_name
        self._use_chroma = False
        self._store: list[dict[str, Any]] = []
        self._collection = None
        self._next_index = 0

        self._use_chroma = False

    def _make_record(self, doc: Document) -> dict[str, Any]:
        meta = dict(doc.metadata) if doc.metadata else {}
        if "doc_id" not in meta:
            meta["doc_id"] = doc.id
        return {
            "id": doc.id,
            "content": doc.content,
            "metadata": meta,
            "embedding": self._embedding_fn(doc.content)
        }

    def _search_records(self, query: str, records: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
        import math
        if not records:
            return []
            
        q_emb = self._embedding_fn(query)
        q_mag = math.sqrt(sum(x*x for x in q_emb))
        
        scored = []
        for r in records:
            r_emb = r["embedding"]
            r_mag = math.sqrt(sum(x*x for x in r_emb))
            if q_mag == 0 or r_mag == 0:
                sim = 0.0
            else:
                sim = _dot(q_emb, r_emb) / (q_mag * r_mag)
            scored.append((sim, r))
            
        scored.sort(key=lambda x: x[0], reverse=True)
        
        results = []
        for sim, r in scored[:top_k]:
            out = dict(r)
            out.pop("embedding", None)
            out["score"] = sim
            results.append(out)
        return results

    def add_documents(self, docs: list[Document]) -> None:
        """
        Embed each document's content and store it.
        For in-memory: append dicts to self._store
        """
        for doc in docs:
            self._store.append(self._make_record(doc))

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """
        Find the top_k most similar documents to query.
        """
        return self._search_records(query, self._store, top_k)

    def get_collection_size(self) -> int:
        """Return the total number of stored chunks."""
        return len(self._store)

    def search_with_filter(self, query: str, top_k: int = 3, metadata_filter: dict = None) -> list[dict]:
        """
        Search with optional metadata pre-filtering.
        """
        candidates = self._store
        if metadata_filter:
            candidates = []
            for r in self._store:
                match = True
                for k, v in metadata_filter.items():
                    if r["metadata"].get(k) != v:
                        match = False
                        break
                if match:
                    candidates.append(r)
        return self._search_records(query, candidates, top_k)

    def delete_document(self, doc_id: str) -> bool:
        """
        Remove all chunks belonging to a document.
        Returns True if any chunks were removed, False otherwise.
        """
        initial_size = len(self._store)
        self._store = [r for r in self._store if r["metadata"].get("doc_id") != doc_id]
        return len(self._store) < initial_size
