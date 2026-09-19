from typing import Callable

from .store import EmbeddingStore


class KnowledgeBaseAgent:
    """
    An agent that answers questions using a vector knowledge base.

    Retrieval-augmented generation (RAG) pattern:
        1. Retrieve top-k relevant chunks from the store.
        2. Build a prompt with the chunks as context.
        3. Call the LLM to generate an answer.
    """

    def __init__(self, store: EmbeddingStore, llm_fn: Callable[[str], str]) -> None:
        self.store = store
        self.llm_fn = llm_fn

    def answer(self, question: str, top_k: int = 3) -> str:
        if self.store.get_collection_size() == 0:
            return "Knowledge base is empty. Cannot answer the question."
            
        chunks = self.store.search(question, top_k=top_k)
        if not chunks:
            return "I couldn't find any relevant information to answer your question."
            
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            source = chunk.get("metadata", {}).get("source_url", chunk.get("id", "Unknown"))
            context_parts.append(f"[{i}] Source: {source}\nContent: {chunk['content']}")
            
        context = "\n\n".join(context_parts)
        prompt = f"""Answer the following question based ONLY on the provided context below. 
If you cannot find the answer in the context, explicitly state that you don't know. Do not hallucinate or make up information.
When using information from the context, you must cite the source by appending its number in brackets, e.g., [1] or [2].

Context:
{context}

Question: {question}

Answer:"""
        return self.llm_fn(prompt)
