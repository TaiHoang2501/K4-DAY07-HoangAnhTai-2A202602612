from __future__ import annotations

import math
import re


class FixedSizeChunker:
    """
    Split text into fixed-size chunks with optional overlap.

    Rules:
        - Each chunk is at most chunk_size characters long.
        - Consecutive chunks share overlap characters.
        - The last chunk contains whatever remains.
        - If text is shorter than chunk_size, return [text].
    """

    def __init__(self, chunk_size: int = 500, overlap: int = 50) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str) -> list[str]:
        if not text:
            return []
        if len(text) <= self.chunk_size:
            return [text]

        step = self.chunk_size - self.overlap
        chunks: list[str] = []
        for start in range(0, len(text), step):
            chunk = text[start : start + self.chunk_size]
            chunks.append(chunk)
            if start + self.chunk_size >= len(text):
                break
        return chunks


class SentenceChunker:
    """
    Split text into chunks of at most max_sentences_per_chunk sentences.

    Sentence detection: split on ". ", "! ", "? " or ".\n".
    Strip extra whitespace from each chunk.
    """

    def __init__(self, max_sentences_per_chunk: int = 3) -> None:
        self.max_sentences_per_chunk = max(1, max_sentences_per_chunk)

    def chunk(self, text: str) -> list[str]:
        if not text:
            return []
        # Tách câu theo dấu chấm, chấm than, hỏi chấm, có khoảng trắng hoặc xuống dòng theo sau
        # Dùng lookbehind (?<=[.!?]) để giữ lại dấu câu ở cuối câu.
        sentences = re.split(r'(?<=[.!?])\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        chunks = []
        for i in range(0, len(sentences), self.max_sentences_per_chunk):
            chunks.append(" ".join(sentences[i:i + self.max_sentences_per_chunk]))
        return chunks


class RecursiveChunker:
    """
    Recursively split text using separators in priority order.

    Default separator priority:
        ["\n\n", "\n", ". ", " ", ""]
    """

    DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

    def __init__(self, separators: list[str] | None = None, chunk_size: int = 500) -> None:
        self.separators = self.DEFAULT_SEPARATORS if separators is None else list(separators)
        self.chunk_size = chunk_size

    def chunk(self, text: str) -> list[str]:
        return self._split(text, self.separators)

    def _split(self, current_text: str, remaining_separators: list[str]) -> list[str]:
        if not current_text:
            return []
        # Base case 1: Text vừa đủ nhỏ
        if len(current_text) <= self.chunk_size:
            return [current_text]
        # Base case 2: Hết separator để thử
        if not remaining_separators:
            return [current_text[i:i+self.chunk_size] for i in range(0, len(current_text), self.chunk_size)]
        
        sep = remaining_separators[0]
        next_seps = remaining_separators[1:]
        
        # Base case 3: separator rỗng
        if sep == "":
            return [current_text[i:i+self.chunk_size] for i in range(0, len(current_text), self.chunk_size)]
            
        splits = current_text.split(sep)
        chunks = []
        current_chunk = ""
        
        for part in splits:
            if current_chunk:
                merged = current_chunk + sep + part
            else:
                merged = part
                
            if len(merged) <= self.chunk_size:
                current_chunk = merged
            else:
                # Chunk hiện tại đã đầy, lưu lại
                if current_chunk:
                    chunks.append(current_chunk)
                
                # Xử lý phần mới (part)
                if len(part) > self.chunk_size:
                    # Đệ quy xuống sâu
                    sub_chunks = self._split(part, next_seps)
                    if sub_chunks:
                        chunks.extend(sub_chunks[:-1])
                        current_chunk = sub_chunks[-1]
                    else:
                        current_chunk = ""
                else:
                    current_chunk = part
                    
        return chunks

class HeadingChunker:
    """
    Split text by Markdown headings (# or ## or ###).
    If a section is too long, recursively split it, but prepend the heading to each sub-chunk.
    """
    def __init__(self, chunk_size: int = 500) -> None:
        self.chunk_size = chunk_size
        self.recursive_chunker = RecursiveChunker(chunk_size=chunk_size)
        
    def chunk(self, text: str) -> list[str]:
        if not text:
            return []
        
        # Tách trước các đoạn heading bằng regex lookahead
        parts = re.split(r'(?m)(?=^#+ )', text)
        chunks = []
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
                
            if len(part) <= self.chunk_size:
                chunks.append(part)
            else:
                lines = part.split("\n")
                heading = lines[0] if lines[0].startswith("#") else ""
                
                sub_chunks = self.recursive_chunker.chunk(part)
                for i, sc in enumerate(sub_chunks):
                    # Giữ nguyên heading cho các đoạn bị cắt vụn
                    if i > 0 and heading and not sc.startswith(heading):
                        sc = heading + "\n" + sc
                    chunks.append(sc)
        return chunks


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def compute_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    cosine_similarity = dot(a, b) / (||a|| * ||b||)

    Returns 0.0 if either vector has zero magnitude.
    """
    mag_a = math.sqrt(sum(x * x for x in vec_a))
    mag_b = math.sqrt(sum(x * x for x in vec_b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return _dot(vec_a, vec_b) / (mag_a * mag_b)


class ChunkingStrategyComparator:
    """Run all built-in chunking strategies and compare their results."""

    def compare(self, text: str, chunk_size: int = 200) -> dict:
        c1 = FixedSizeChunker(chunk_size=chunk_size).chunk(text)
        c2 = SentenceChunker(max_sentences_per_chunk=3).chunk(text)
        c3 = RecursiveChunker(chunk_size=chunk_size).chunk(text)
        
        def stats(chunks):
            if not chunks:
                return {"count": 0, "avg_length": 0.0, "chunks": []}
            return {
                "count": len(chunks),
                "avg_length": sum(len(c) for c in chunks) / len(chunks),
                "chunks": chunks
            }
            
        return {
            "fixed_size": stats(c1),
            "by_sentences": stats(c2),
            "recursive": stats(c3)
        }
