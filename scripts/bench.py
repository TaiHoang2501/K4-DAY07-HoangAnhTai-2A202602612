"""Benchmark tool — đo chất lượng retrieval trên 5 câu hỏi đánh giá.

Pipeline:
  1. Đọc từng file .md, tách frontmatter thành metadata và phần thân thành content
  2. Chunk phần thân, mỗi chunk thành một Document:
        Document(id=f"{path.stem}#{i}", content=chunk,
                 metadata={**frontmatter, "doc_id": path.stem, ...})
  3. Nạp vào EmbeddingStore, chạy 5 query qua search_with_filter()
  4. In top-3 kèm score và doc_id để đối chiếu với gold answer

Nâng cấp:
  - Chấm 2 mức: gold_snippet phải xuất hiện trong context (không chỉ doc_id)
  - A/B test: câu cần filter chạy 2 lần (có/không filter)
  - Phân tích lỗi tự động
  - Xuất ket_qua_benchmark.txt

Mỗi người chỉ đổi MỘT dòng — dòng chọn chunker — sang chiến lược của mình.
"""
import hashlib
import json
import os
import sys
from io import StringIO
from pathlib import Path
import re

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.chunking import HeadingChunker, RecursiveChunker, SentenceChunker, FixedSizeChunker
from src.store import EmbeddingStore
from src.models import Document
from src.embeddings import (
    EMBEDDING_PROVIDER_ENV,
    GEMINI_EMBEDDING_MODEL,
    LOCAL_EMBEDDING_MODEL,
    OPENAI_EMBEDDING_MODEL,
    GeminiEmbedder,
    LocalEmbedder,
    OpenAIEmbedder,
    _mock_embed,
)

# ─── Embedding cache (tránh tốn tiền khi chạy lại) ────────────────────────
CACHE_FILE = Path(__file__).parent / ".embedding_cache.json"


def _load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def _make_cached_embedder(base_fn):
    """Wrap một embedder bất kỳ bằng cache theo hash nội dung."""
    cache = _load_cache()
    backend_name = getattr(base_fn, "_backend_name", base_fn.__class__.__name__)

    def cached_embed(text: str) -> list[float]:
        key = hashlib.sha256((backend_name + "|" + text).encode()).hexdigest()
        if key in cache:
            return cache[key]
        vec = base_fn(text)
        cache[key] = vec
        _save_cache(cache)
        return vec

    cached_embed._backend_name = f"{backend_name} (cached)"
    return cached_embed


# ─── Chọn embedder theo .env ──────────────────────────────────────────────
def get_embedder():
    load_dotenv(override=False)
    provider = os.getenv(EMBEDDING_PROVIDER_ENV, "mock").strip().lower()

    if provider == "local":
        try:
            emb = LocalEmbedder(model_name=os.getenv("LOCAL_EMBEDDING_MODEL", LOCAL_EMBEDDING_MODEL))
            return emb
        except Exception as e:
            print(f"⚠ LocalEmbedder failed ({e}), falling back to mock")
            return _mock_embed
    elif provider == "openai":
        try:
            base = OpenAIEmbedder(model_name=os.getenv("OPENAI_EMBEDDING_MODEL", OPENAI_EMBEDDING_MODEL))
            return _make_cached_embedder(base)
        except Exception:
            return _mock_embed
    elif provider == "gemini":
        try:
            base = GeminiEmbedder(model_name=os.getenv("GEMINI_EMBEDDING_MODEL", GEMINI_EMBEDDING_MODEL))
            return _make_cached_embedder(base)
        except Exception:
            return _mock_embed
    else:
        return _mock_embed


# ─── 5 câu benchmark ──────────────────────────────────────────────────────
# gold_snippet: chuỗi đặc trưng PHẢI xuất hiện trong context truy xuất được
# để chứng minh chunk thực sự chứa đáp án, không chỉ cùng doc.
BENCHMARK_QUERIES = [
    {
        "query": "Học bổng KKHT loại xuất sắc (loại A) được tính như thế nào?",
        "filter": {"audience": "student"},
        "gold_answer": "Loại xuất sắc (loại A): bằng 1,5 lần mức học bổng loại khá.",
        "gold_doc": "hust-kkht-criteria-student",
        "gold_snippet": "1,5 lần",
    },
    {
        "query": "Sinh viên từ K67 đến K70 cần đạt điều kiện gì để đăng ký xét học bổng Trần Đại Nghĩa?",
        "filter": None,
        "gold_answer": "Đang trong thời gian học tập theo thiết kế CTĐT chuẩn; GPA HK 2025.2 ≥ 2,0; Điểm rèn luyện HK 2025.2 ≥ 50.",
        "gold_doc": "hust-tran-dai-nghia-2026-1",
        "gold_snippet": "2,0",
    },
    {
        "query": "Sinh viên đăng ký xét học bổng Trần Đại Nghĩa ở đâu và trước ngày nào?",
        "filter": None,
        "gold_answer": "Đăng ký trên eHUST hoặc qldt.hust.edu.vn, nộp hồ sơ giấy tại phòng 102 nhà C1 trước 16h30 thứ Sáu ngày 09/10/2026.",
        "gold_doc": "hust-tran-dai-nghia-2026-1",
        "gold_snippet": "phòng 102",
    },
    {
        "query": "Sinh viên bị cảnh báo học tập có được xét cấp học bổng KKHT không?",
        "filter": {"audience": "student"},
        "gold_answer": "Không. Bị cảnh báo học tập từ mức 1 trở lên thì không được xét cấp học bổng KKHT.",
        "gold_doc": "hust-kkht-criteria-student",
        "gold_snippet": "cảnh báo học tập",
    },
    {
        "query": "Kết quả xét cấp học bổng KKHT kỳ II 2025-2026 có bao nhiêu sinh viên mỗi loại A, B, C?",
        "filter": None,
        "gold_answer": "1.343 SV loại Xuất sắc (A), 456 SV loại Giỏi (B), 89 SV loại Khá (C). Tổng 1.888 SV.",
        "gold_doc": "hust-kkht-results-2025-2",
        "gold_snippet": "1.343",
    },
]


class TeeOutput:
    """Ghi đồng thời ra stdout và StringIO buffer."""
    def __init__(self):
        self.buffer = StringIO()

    def print(self, *args, **kwargs):
        line = StringIO()
        print(*args, file=line, **kwargs)
        text = line.getvalue()
        sys.stdout.write(text)
        self.buffer.write(text)

    def get_text(self):
        return self.buffer.getvalue()


def score_result(results: list[dict], gold_doc: str, gold_snippet: str) -> tuple[int, str]:
    """Chấm 2 mức theo SCORING.md.

    Returns: (score, explanation)
        2 = gold doc ở top-1 VÀ context chứa gold_snippet
        1 = gold doc ở top-2 hoặc top-3 (có snippet trong top-3)
        0 = gold doc vắng khỏi top-3 HOẶC context không chứa snippet
    """
    # Tìm vị trí gold doc trong top-3
    gold_rank = None
    for i, r in enumerate(results):
        if r["metadata"].get("doc_id") == gold_doc:
            gold_rank = i + 1
            break

    # Kiểm tra gold_snippet có trong bất kỳ chunk top-3 nào không
    snippet_found = any(gold_snippet.lower() in r["content"].lower() for r in results)

    if gold_rank is None:
        return 0, "Gold doc vắng khỏi top-3"
    if not snippet_found:
        return 0, f"Gold doc ở top-{gold_rank} nhưng KHÔNG chunk nào chứa snippet '{gold_snippet}'"
    if gold_rank == 1:
        return 2, f"Top-1 đúng doc + context chứa '{gold_snippet}'"
    return 1, f"Gold doc ở top-{gold_rank}, context chứa snippet"


def load_chunks(data_dir: Path, chunker) -> list[Document]:
    """Đọc .md, tách frontmatter, chunk, trả về list[Document]."""
    docs = []
    for p in sorted(data_dir.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                fm_text = parts[1]
                content = parts[2].strip()
                fm = dict(re.findall(r'^(\w+):\s*(.+)$', fm_text, re.M))
                fm = {k: v.strip('"\'') for k, v in fm.items()}

                chunks = chunker.chunk(content)
                for i, c in enumerate(chunks):
                    meta = dict(fm)
                    meta["doc_id"] = p.stem
                    docs.append(Document(
                        id=f"{p.stem}#{i}",
                        content=c,
                        metadata=meta,
                    ))
    return docs


def run_query(out, store, bq, idx, label=""):
    """Chạy 1 query, in kết quả, trả về (score, results)."""
    query = bq["query"]
    filter_dict = bq["filter"] if "use_filter" not in bq else (bq["filter"] if bq["use_filter"] else None)
    gold = bq["gold_answer"]
    gold_doc = bq["gold_doc"]
    gold_snippet = bq["gold_snippet"]

    out.print(f"\n{'─' * 70}")
    out.print(f"Q{idx}{label}: {query}")
    out.print(f"  Filter: {filter_dict}")
    out.print(f"  Gold Answer: {gold}")
    out.print(f"  Gold Doc: {gold_doc} | Gold Snippet: '{gold_snippet}'")
    out.print()

    results = store.search_with_filter(query, top_k=3, metadata_filter=filter_dict)

    for i, r in enumerate(results, 1):
        doc_id = r["metadata"].get("doc_id", "?")
        score = r["score"]
        preview = r["content"][:150].replace("\n", " ")
        has_snippet = gold_snippet.lower() in r["content"].lower()
        markers = []
        if doc_id == gold_doc:
            markers.append("DOC✅")
        if has_snippet:
            markers.append("SNIPPET✅")
        marker_str = " ".join(markers) if markers else ""
        out.print(f"  [{i}] score={score:.4f} doc_id={doc_id}  {marker_str}")
        out.print(f"       {preview}...")

    pts, explanation = score_result(results, gold_doc, gold_snippet)
    emoji = {2: "🟢", 1: "🟡", 0: "🔴"}[pts]
    out.print(f"  → {emoji} Score: {pts}/2 — {explanation}")

    return pts, results


def main():
    data_dir = Path("data/hoc-bong-hust")
    if not data_dir.exists():
        print(f"⚠ Thư mục {data_dir} không tồn tại!")
        return

    out = TeeOutput()

    # Chọn embedder
    embedder = get_embedder()
    backend_name = getattr(embedder, '_backend_name', embedder.__class__.__name__)
    out.print(f"Embedding backend: {backend_name}")

    if "mock" in backend_name.lower():
        out.print("⚠ ĐANG DÙNG MOCK EMBEDDER — số liệu score là nhiễu, không phản ánh ngữ nghĩa!")
        out.print("  Đặt EMBEDDING_PROVIDER=local trong .env để dùng sentence-transformers.")

    # ╔═══════════════════════════════════════════════════════════════╗
    # ║  Mỗi người chỉ đổi DÒNG NÀY sang chunker của mình          ║
    # ╚═══════════════════════════════════════════════════════════════╝
    chunker = HeadingChunker(chunk_size=500)

    docs = load_chunks(data_dir, chunker)
    store = EmbeddingStore(embedding_fn=embedder)
    store.add_documents(docs)
    out.print(f"Loaded {len(docs)} chunks into store (chunker: {chunker.__class__.__name__}).\n")

    # Thống kê chunk
    doc_ids = sorted(set(d.metadata.get("doc_id") for d in docs))
    for did in doc_ids:
        count = sum(1 for d in docs if d.metadata.get("doc_id") == did)
        out.print(f"  {did}: {count} chunks")
    out.print()

    # ═══════════════════════════════════════════════════════════════
    # PHẦN 1: Chạy 5 câu benchmark chính
    # ═══════════════════════════════════════════════════════════════
    out.print("=" * 70)
    out.print("PHẦN 1: BENCHMARK CHÍNH (5 câu)")
    out.print("=" * 70)

    total_score = 0
    for idx, bq in enumerate(BENCHMARK_QUERIES, 1):
        pts, _ = run_query(out, store, bq, idx)
        total_score += pts

    out.print(f"\n{'=' * 70}")
    out.print(f"TỔNG ĐIỂM: {total_score} / {len(BENCHMARK_QUERIES) * 2}")
    out.print(f"{'=' * 70}")

    # ═══════════════════════════════════════════════════════════════
    # PHẦN 2: A/B TEST — filter vs no-filter cho Q1 và Q4
    # ═══════════════════════════════════════════════════════════════
    out.print(f"\n\n{'=' * 70}")
    out.print("PHẦN 2: A/B TEST — có filter vs không filter")
    out.print("=" * 70)

    filter_queries = [bq for bq in BENCHMARK_QUERIES if bq["filter"] is not None]
    for bq in filter_queries:
        idx = BENCHMARK_QUERIES.index(bq) + 1

        # Chạy VỚI filter
        pts_with, results_with = run_query(out, store, bq, idx, label=" [CÓ FILTER]")

        # Chạy KHÔNG filter
        bq_no_filter = dict(bq)
        bq_no_filter["use_filter"] = False
        pts_without, results_without = run_query(out, store, bq_no_filter, idx, label=" [KHÔNG FILTER]")

        # So sánh
        out.print(f"\n  📊 So sánh Q{idx}: CÓ filter={pts_with}/2 vs KHÔNG filter={pts_without}/2")
        if pts_with > pts_without:
            out.print("  → ✅ Filter GIÚP ÍCH — loại bỏ tài liệu sai audience")
        elif pts_with == pts_without:
            out.print("  → ⚪ Filter KHÔNG thay đổi kết quả")
            # Kiểm tra xem top-3 có khác không
            ids_with = [r["metadata"].get("doc_id") for r in results_with]
            ids_without = [r["metadata"].get("doc_id") for r in results_without]
            if ids_with != ids_without:
                out.print(f"     Tuy nhiên thứ tự khác: {ids_with} vs {ids_without}")
        else:
            out.print("  → ⚠ Filter LÀM GIẢM — filter quá cứng loại nhầm doc có đáp án")

    # ═══════════════════════════════════════════════════════════════
    # PHẦN 3: PHÂN TÍCH LỖI
    # ═══════════════════════════════════════════════════════════════
    out.print(f"\n\n{'=' * 70}")
    out.print("PHẦN 3: PHÂN TÍCH LỖI (FAILURE ANALYSIS)")
    out.print("=" * 70)

    failures = []
    for idx, bq in enumerate(BENCHMARK_QUERIES, 1):
        results = store.search_with_filter(bq["query"], top_k=3, metadata_filter=bq["filter"])
        pts, explanation = score_result(results, bq["gold_doc"], bq["gold_snippet"])
        if pts < 2:
            failures.append((idx, bq, pts, explanation, results))

    if not failures:
        out.print("\n🎉 Không có failure case — tất cả 5 câu đạt 2/2!")
    else:
        for idx, bq, pts, explanation, results in failures:
            out.print(f"\n❌ FAILURE Q{idx}: {bq['query']}")
            out.print(f"   Score: {pts}/2 — {explanation}")

            # Phân tích nguyên nhân
            top1_doc = results[0]["metadata"].get("doc_id") if results else "N/A"
            top1_has_snippet = bq["gold_snippet"].lower() in results[0]["content"].lower() if results else False
            gold_in_top3 = any(r["metadata"].get("doc_id") == bq["gold_doc"] for r in results)
            snippet_in_top3 = any(bq["gold_snippet"].lower() in r["content"].lower() for r in results)

            if not gold_in_top3:
                out.print(f"   NGUYÊN NHÂN: Gold doc '{bq['gold_doc']}' hoàn toàn vắng khỏi top-3.")
                out.print(f"   Top-3 doc_ids: {[r['metadata'].get('doc_id') for r in results]}")
                if bq["filter"]:
                    out.print(f"   → Có thể filter {bq['filter']} quá cứng, hoặc chunk gold quá ngắn/ít từ khóa.")
                else:
                    out.print(f"   → Chunk chứa đáp án có thể quá ngắn so với các chunk cùng chủ đề từ doc khác.")
                out.print(f"   ĐỀ XUẤT: Tăng overlap hoặc thử chunker giữ nguyên section heading.")
            elif gold_in_top3 and not snippet_in_top3:
                out.print(f"   NGUYÊN NHÂN: Gold doc có trong top-3 nhưng KHÔNG chunk nào chứa đáp án.")
                out.print(f"   → Chunker cắt đúng doc nhưng sai section — cosine đo chủ đề, không đo mật độ đáp án.")
                out.print(f"   ĐỀ XUẤT: Dùng HeadingChunker để giữ nguyên section, hoặc tăng chunk_size.")
            elif top1_doc != bq["gold_doc"]:
                out.print(f"   NGUYÊN NHÂN: Top-1 là '{top1_doc}' (sai doc), gold doc ở vị trí thấp hơn.")
                out.print(f"   → Doc khác có chủ đề gần hơn về mặt embedding, dù không chứa đáp án chính xác.")
                out.print(f"   ĐỀ XUẤT: Thêm metadata filter hoặc cải thiện câu hỏi để cụ thể hơn.")
            elif not top1_has_snippet and top1_doc == bq["gold_doc"]:
                out.print(f"   NGUYÊN NHÂN: Top-1 đúng doc nhưng SAI section — chunk khác trong cùng doc chứa đáp án.")
                out.print(f"   → Các section cùng doc có score gần bằng nhau, section nào lọt top gần như ngẫu nhiên.")
                out.print(f"   ĐỀ XUẤT: Giảm chunk_size để mỗi chunk tập trung hơn, hoặc thêm overlap.")

    # ═══════════════════════════════════════════════════════════════
    # LƯU KẾT QUẢ
    # ═══════════════════════════════════════════════════════════════
    output_file = Path("ket_qua_benchmark.txt")
    output_file.write_text(out.get_text(), encoding="utf-8")
    print(f"\n📁 Đã lưu kết quả vào: {output_file.resolve()}")


if __name__ == "__main__":
    main()
