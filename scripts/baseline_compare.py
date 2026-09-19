"""Baseline Analysis — so sánh 3 chiến lược chunking trên 3 tài liệu.

Bỏ frontmatter trước khi so sánh để không đo cả khối YAML.
Output: bảng chunk count, avg length, mẫu chunk đầu tiên.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.chunking import ChunkingStrategyComparator


# 3 tài liệu đại diện
FILES = [
    "data/hoc-bong-hust/hust-kkht-criteria-student.md",
    "data/hoc-bong-hust/hust-tran-dai-nghia-2026-1.md",
    "data/hoc-bong-hust/hust-kkht-council-staff.md",
]


def strip_frontmatter(text: str) -> str:
    """Bỏ YAML frontmatter (nằm giữa cặp ---) ở đầu file."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return text


def main():
    comparator = ChunkingStrategyComparator()

    for file_path in FILES:
        p = Path(file_path)
        if not p.exists():
            print(f"⚠ File not found: {p}")
            continue

        raw = p.read_text(encoding="utf-8")
        content = strip_frontmatter(raw)

        print(f"\n{'=' * 70}")
        print(f"📄 {p.name}  ({len(content)} ký tự sau khi bỏ frontmatter)")
        print(f"{'=' * 70}")

        results = comparator.compare(content, chunk_size=200)

        # In bảng
        print(f"{'Chiến lược':<20} {'Số chunk':>10} {'Avg length':>12}")
        print("-" * 44)
        for strategy_name, stats in results.items():
            print(f"{strategy_name:<20} {stats['count']:>10} {stats['avg_length']:>12.1f}")

        # In mẫu chunk đầu tiên của mỗi chiến lược
        print(f"\n--- Mẫu chunk đầu tiên ---")
        for strategy_name, stats in results.items():
            if stats["chunks"]:
                preview = stats["chunks"][0][:120].replace("\n", "↵")
                print(f"  [{strategy_name}] {preview}...")
        print()


if __name__ == "__main__":
    main()
