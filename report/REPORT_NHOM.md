# Báo Cáo Nhóm — Lab 7: Embedding & Vector Store

**Nhóm:** Học bổng HUST
**Thành viên:** Trần Nguyễn Tiến Đức (2A202602871), Lê Nguyễn Quốc Bảo (2A202603011), Hoàng Anh Tài (2A202602612), Nguyễn Anh Dũng (2A202602554)
**Ngày:** 2026-09-19

> **Nộp 1 bản / nhóm.** Phần cá nhân (hướng tiếp cận, kết quả riêng, dự đoán…) mỗi thành viên nộp riêng trong `REPORT_CANHAN.md`. Chi tiết thang điểm: `docs/SCORING.md`.

**Tổng điểm phần nhóm: 40** = Lựa chọn tài liệu (10) + Thiết kế chiến lược (15) + Chất lượng truy xuất (10) + Thuyết trình (5).

---

## 1. Lựa chọn tài liệu (Document Set Quality) — Nhóm (10 điểm)

### Chủ đề (Domain) & Lý Do Chọn

**Chủ đề:** Học bổng và hỗ trợ tài chính sinh viên — Đại học Bách khoa Hà Nội (HUST)

**Tại sao nhóm chọn chủ đề này?**
> Thông báo học bổng trên Cổng thông tin đào tạo HUST là văn bản công khai, có số liệu (GPA, mức tiền, hạn nộp) và heading rõ để so sánh chunking. Cùng chủ đề KKHT có hai góc nhìn khác nhau: tiêu chuẩn dành cho sinh viên và quy trình Hội đồng/quỹ dành cho cán bộ — đủ điều kiện lọc `audience`.

### Danh sách tài liệu (Data Inventory)

| # | Tên tài liệu | Nguồn (Source URL) | Ngày lấy / Phiên bản | Số ký tự | Metadata đã gán |
|---|--------------|------------|--------------------|----------|-----------------|
| 1 | hust-tran-dai-nghia-2026-1 | https://ctt.hust.edu.vn/DisplayWeb/DisplayBaiViet?baiviet=51636 | 2026-09-19 / not-stated | 3467 | audience=student, department=student-affairs, category=scholarship, language=vi |
| 2 | hust-mb-chasing-2025 | https://ctt.hust.edu.vn/DisplayWeb/DisplayBaiViet?baiviet=46593 | 2026-09-19 / not-stated | 933 | audience=student, department=student-affairs, category=scholarship, language=vi |
| 3 | hust-kkht-eligibility-2025-2 | https://ctt.hust.edu.vn/DisplayWeb/DisplayBaiViet?baiviet=46614 | 2026-09-19 / not-stated | 1438 | audience=student, department=student-affairs, category=scholarship, language=vi |
| 4 | hust-lg-scholarship-2025 | https://ctt.hust.edu.vn/DisplayWeb/DisplayBaiViet?baiviet=46587 | 2026-09-19 / not-stated | 2227 | audience=student, department=student-affairs, category=scholarship-and-career, language=vi |
| 5 | hust-kkht-results-2025-2 | https://ctt.hust.edu.vn/DisplayWeb/DisplayBaiViet?baiviet=49616 | 2026-09-19 / not-stated | 1040 | audience=student, department=student-affairs, category=scholarship, language=vi |
| 6 | hust-kkht-criteria-student | https://ctt.hust.edu.vn/Upload/Nguyen%20Viet%20Tien/files/Quy%20%C4%91%E1%BB%8Bnh%20v%E1%BB%81%20vi%E1%BB%87c%20x%C3%A9t%20c%E1%BA%A5p%20HB%20KKHT.pdf | 2026-09-19 / 2124/QĐ-ĐHBK | 1999 | audience=student, department=student-affairs, category=scholarship, language=vi |
| 7 | hust-kkht-council-staff | cùng PDF 2124/QĐ-ĐHBK (tách phần Hội đồng/quỹ) | 2026-09-19 / 2124/QĐ-ĐHBK | 1353 | audience=staff, department=student-affairs, category=scholarship-admin, language=vi |

**Danh sách kiểm tra quản trị dữ liệu (Data governance checklist):**
- [x] Tập tài liệu (Corpus) chỉ chứa nguồn công khai/được phép dùng và không chứa dữ liệu cá nhân, thông tin đăng nhập hoặc tài liệu nội bộ.
- [x] Mỗi tài liệu có `source_url`, `retrieved_at`, `document_version` (hoặc ngày hiệu lực) trong metadata.

### Cấu trúc Metadata (Metadata Schema)

| Trường metadata | Kiểu | Ví dụ giá trị | Tại sao hữu ích cho truy xuất (retrieval)? |
|----------------|------|---------------|-------------------------------|
| audience | enum | student / staff | Lọc câu hỏi của sinh viên khỏi tài liệu Hội đồng/quỹ dành cho cán bộ |
| department | string | student-affairs | Gom tài liệu cùng đơn vị quản lý học bổng |
| category | string | scholarship / scholarship-admin / scholarship-and-career | Tách học bổng học tập, học bổng doanh nghiệp, và quy trình xét duyệt |
| language | string | vi | Corpus tiếng Việt; sẵn sàng nếu sau này thêm bản tiếng Anh |
| document_version | string | 2124/QĐ-ĐHBK hoặc not-stated | Tránh lấy thông báo cũ hơn quy định đang hiệu lực |
| retrieved_at | date | 2026-09-19 | Truy vết ngày lấy nguồn |

---

## 2. Thiết kế chiến lược (Strategy Design) — Nhóm (15 điểm)

> Mỗi thành viên thử **một chiến lược khác nhau** trên cùng bộ tài liệu; nhóm tổng hợp và so sánh ở đây.

### Phân tích đường cơ sở (Baseline Analysis)

Chạy `ChunkingStrategyComparator().compare()` trên 2-3 tài liệu:

| Tài liệu | Chiến lược (Strategy) | Số lượng Chunk | Độ dài trung bình | Giữ được ngữ cảnh không? |
|-----------|----------|-------------|------------|-------------------|
| hust-kkht-criteria-student | FixedSizeChunker (`fixed_size`) | 13 | 199.9 | Cắt giữa điều khoản khi hết 200 ký tự |
| hust-kkht-criteria-student | SentenceChunker (`by_sentences`) | 7 | 284.0 | Giữ ranh giới câu; một số list vẫn dính nhau |
| hust-kkht-criteria-student | RecursiveChunker (`recursive`) | 17 | 116.1 | Nhiều chunk ngắn, bám `\n\n`/`\n` |
| hust-tran-dai-nghia-2026-1 | FixedSizeChunker (`fixed_size`) | 23 | 198.6 | Cắt giữa nhóm đối tượng |
| hust-tran-dai-nghia-2026-1 | SentenceChunker (`by_sentences`) | 10 | 344.9 | Ít chunk hơn, vẫn có đoạn dài |
| hust-tran-dai-nghia-2026-1 | RecursiveChunker (`recursive`) | 32 | 106.8 | Tách list/heading mịn, dễ mất ngữ cảnh vì chunk ngắn |
| hust-lg-scholarship-2025 | FixedSizeChunker (`fixed_size`) | 15 | 195.1 | Cắt giữa mô tả vị trí |
| hust-lg-scholarship-2025 | SentenceChunker (`by_sentences`) | 8 | 277.0 | Giữ câu; mục bullet vẫn bị gộp |
| hust-lg-scholarship-2025 | RecursiveChunker (`recursive`) | 20 | 110.0 | Tách theo mục vị trí/quyền lợi |

### Chiến lược của từng thành viên

> Mỗi thành viên điền một khối dưới đây (copy thêm nếu nhóm có nhiều hơn 3 người).

**Thành viên 1 — Trần Nguyễn Tiến Đức (2A202602871), nhóm trưởng**
- **Loại chiến lược:** RecursiveChunker
- **Mô tả & lý do chọn cho chủ đề này:** Thông báo học bổng HUST có đoạn, list và heading Markdown. Recursive ưu tiên `\n\n` rồi `\n`. `chunk_size=900` (không phải 500) để tiêu đề + bảng GPA loại A/B/C nằm cùng một chunk — nếu cắt sớm, retrieval đúng file nhưng sai đoạn.
- **Code snippet (nếu custom):** không — dùng `RecursiveChunker(chunk_size=900)` trong `bench.py`.

**Thành viên 2 — Lê Nguyễn Quốc Bảo (2A202603011)**
- **Loại chiến lược:** FixedSizeChunker (`chunk_size=500`, `overlap=50`)
- **Mô tả & lý do chọn:** Baseline lab, cửa sổ cố định. Trên corpus HUST vô tình gom được Điều 3 (GPA 3,6) vào một chunk nên điểm OpenAI cao nhất (8/10). Điểm yếu: cắt giữa câu.
- **Code snippet (nếu custom):** không — `FixedSizeChunker(chunk_size=500, overlap=50)` (đã có sẵn).

**Thành viên 3 — Hoàng Anh Tài (2A202602612)**
- **Loại chiến lược:** SentenceChunker (`max_sentences_per_chunk=3`)
- **Mô tả & lý do chọn:** Giữ ranh giới câu. Văn tiếng Việt ít `. ` nên chunk to hơn Recursive; câu 3–4 (hạn nộp, số SV) vào top-1. Câu 5 tách `10–30 triệu` khỏi hạn `09/01/2026`.
- **Code snippet (nếu custom):** không — `SentenceChunker(max_sentences_per_chunk=3)`.

**Thành viên 4 — Nguyễn Anh Dũng (2A202602554) (ràng buộc L3A: chunk theo heading)**
- **Loại chiến lược:** HeadingChunker (custom)
- **Mô tả & lý do chọn:** Thông báo/quy định HUST viết theo `##`. Tách trước mỗi heading; section dài thì recursive; **gắn H1 + heading mục** vào từng mảnh con. Sau khi gắn H1, câu 5 lấy đúng `## Thời hạn` top-1; câu 1–2 vẫn hay nhầm `## Mức học bổng` với Điều 3.
- **Code snippet (nếu custom):**
```python
# src/chunking.py — HeadingChunker
# split bằng (?=^#{1,6}\s); nếu section > chunk_size thì RecursiveChunker
# rồi f"{heading}\n\n{piece}" cho mỗi mảnh con
CHUNKER = HeadingChunker(chunk_size=800)
```

### So Sánh Giữa Các Thành Viên

> Chạy trên **cùng** `bench.py`, **cùng** 5 câu, **cùng** OpenAI `text-embedding-3-small`. Thành viên khác chỉ đổi 1 dòng CHUNKER.

| Thành viên | Chiến lược (Strategy) | Điểm truy xuất (/10) | Điểm mạnh | Điểm yếu |
|-----------|----------|----------------------|-----------|----------|
| Trần Nguyễn Tiến Đức | RecursiveChunker (900) | **9/10** | Câu 1–4 top-1+span; A/B câu 2 staff hạng 2 khi không filter | Câu 5: `10–30 triệu` và `09/01/2026` bị tách hai mục |
| Lê Nguyễn Quốc Bảo | FixedSizeChunker | 8/10 | Câu 1 gom được Điều 3; filter câu 2 đưa span GPA vào hạng 3 | Cắt giữa câu; câu 2 span không top-1 |
| Hoàng Anh Tài | SentenceChunker | 6/10 | Câu 3–4 top-1+span | Câu 5 đúng file nhưng tách tiền khỏi hạn |
| Nguyễn Anh Dũng | HeadingChunker | 7/10 | Câu 5 đúng `## Thời hạn` top-1; gắn H1 vào mọi mục | Câu 1–2 nhầm `## Mức học bổng` với Điều 3 (span hạng 2) |

**Chiến lược nào tốt nhất cho chủ đề này? Tại sao?**
> **Recursive `chunk_size=900` (9/10)** thắng trên corpus này vì giữ tiêu đề + bảng GPA trong một chunk, vẫn tách được hạn nộp Trần Đại Nghĩa. Heading (7/10) đúng hướng quy định (`##`) nhưng model nhầm “mức học bổng” với “tiêu chuẩn GPA”. FixedSize 8/10 gần sát nhưng cắt giữa câu. Điểm cao không thay cho giải thích span vs `doc_id`.

---

## 3. Câu hỏi đánh giá & Chất lượng truy xuất (Retrieval Quality) — Nhóm (10 điểm)

### Câu hỏi đánh giá & Câu trả lời chuẩn (nhóm thống nhất)

> **Đúng 5 câu hỏi**, đa dạng, có thể kiểm chứng; **ít nhất 1 câu** cần lọc metadata mới trả lời tốt. Đây là bộ câu hỏi chung cho mọi thành viên chạy.

| # | Câu hỏi (Query) | Câu trả lời chuẩn (Gold Answer) | Chunk nào chứa thông tin? |
|---|-------|-------------------------------|--------------------------|
| 1 | GPA và điểm rèn luyện tối thiểu để đạt học bổng KKHT loại A là bao nhiêu? | Loại A: GPA ≥ 3,6 và điểm rèn luyện học kỳ ≥ 90 điểm. | `hust-kkht-criteria-student` — mục Tiêu chuẩn xét cấp (Điều 3) |
| 2 | Tiêu chuẩn xét cấp học bổng KKHT là gì? **(cần `metadata_filter={"audience":"student"}`)** | Loại C: GPA ≥ 2,5 / rèn luyện ≥ 65; loại B: GPA ≥ 3,2 / ≥ 80; loại A: GPA ≥ 3,6 / ≥ 90. | `hust-kkht-criteria-student`. Không lọc sẽ lẫn `hust-kkht-council-staff` (Hội đồng, quỹ 8%). |
| 3 | Hạn nộp hồ sơ học bổng Trần Đại Nghĩa học kỳ I năm học 2026-2027 là khi nào và nộp ở đâu? | eHUST hoặc qldt.hust.edu.vn mục học bổng; hồ sơ giấy phòng 102 nhà C1 trước 16h30 thứ Sáu 09/10/2026. | `hust-tran-dai-nghia-2026-1` — mục 4. Quy trình đăng ký |
| 4 | Kỳ II năm học 2025-2026 có bao nhiêu sinh viên được học bổng KKHT loại A, B và C? | 1.888 sinh viên: 1.343 loại A, 456 loại B, 89 loại C. | `hust-kkht-results-2025-2` |
| 5 | Học bổng MB The Best of MB Chasing 2025 trị giá bao nhiêu và hạn đăng ký là khi nào? | 10–30 triệu VNĐ/sinh viên; hạn đăng ký 09/01/2026. | `hust-mb-chasing-2025` — mục Quyền lợi / Thời hạn |

### Tổng hợp chất lượng truy xuất của nhóm

> Cách chấm (theo `docs/SCORING.md`): **2 điểm/câu** — top-3 chứa chunk liên quan + agent trả lời đúng (2), có liên quan nhưng thiếu/không ở top-1 (1), không có trong top-3 (0).

| # | Câu hỏi | Chiến lược tốt nhất cho câu này | Có chunk liên quan trong top-3? | Ghi chú |
|---|---------|-------------------------------|-------------------------------|---------|
| 1 | GPA loại A | Recursive (2/2) | Có, top-1 chứa `GPA ≥ 3,6` | Heading: Điều 3 hạng 2 (1/2) vì nhầm `## Mức học bổng` |
| 2 | Tiêu chuẩn KKHT (filter student) | Recursive (2/2) | Có span GPA top-1 khi có filter | A/B: không filter `council-staff` hạng 2 |
| 3 | Hạn nộp Trần Đại Nghĩa | Recursive / Sentence (2/2) | Có `09/10/2026` top-1 | Heading span hạng 3 (đúng file, sai mục hồ sơ) |
| 4 | Số SV A/B/C kỳ 2025.2 | Cả 4 chiến lược (2/2) | Có `1.343` top-1 | Một đoạn chứa đủ 3 số |
| 5 | MB Chasing tiền + hạn | Heading (2/2) | Có `09/01/2026` top-1 (`## Thời hạn`) | Recursive: ngày hạn hạng 3 (1/2) |

**Lọc bằng metadata có giúp ích không? Ở câu hỏi nào?**
> Có, **câu 2**. Recursive: không filter thì `hust-kkht-council-staff` hạng 2 (Hội đồng/quỹ 8%); `audience=student` loại file staff, gold Điều 3 giữ top-1. Filter **không làm mất** đáp án sinh viên trên Recursive 900; với FixedSize, filter mới đưa span GPA vào top-3 (recall staff mất, precision student tăng). Đó là đánh đổi thu hồi/chính xác đúng như `docs/EVALUATION.md`.

---

## 4. Thuyết trình (Demo) & Bài học nhóm — Nhóm (5 điểm)

**Những phân tích (insights) hay nhất nhóm sẽ trình bày:**
> 1. Failure case còn lại — câu 5 Recursive: top-1 đúng file MB nhưng chunk intro **không** có `09/01/2026` (ngày nằm `## Thời hạn` hạng 3). Chấm `doc_id` = 2đ; chấm span = 1đ.
> 2. A/B câu 2: không filter → `council-staff` hạng 2; có `audience=student` → staff biến mất. Recursive 900 vẫn giữ Điều 3 top-1 cả hai lần.
> 3. Phân bố score OpenAI ~0.55–0.87, tách rõ gold vs nhiễu; mock trước đó ~0.14–0.32 nên ranking ngẫu nhiên.

**Bài học rút ra khi so sánh trong nhóm:**
> Cùng 7 file / 5 câu, điểm 6–9/10 khác nhau chỉ vì ranh giới chunk. Recursive 900 giữ GPA với tiêu đề (9/10); Heading thắng câu hạn MB vì tách `## Thời hạn`; Sentence cắt ngày khỏi số tiền. Không chấm chỉ bằng `doc_id`.

**Nếu làm lại, nhóm sẽ thay đổi gì trong chiến lược dữ liệu (data strategy)?**
> Để hạn đăng ký và mức tiền trong **cùng một mục** (câu 5). Giữ 1–2 câu số liệu ngay dưới mỗi `##`. Dùng OpenAI từ đầu, khỏi HuggingFace.

---

## Tự Đánh Giá (Phần Nhóm)

| Tiêu chí | Điểm tự đánh giá |
|----------|-------------------|
| Lựa chọn tài liệu (Document Set Quality) | 9 / 10 |
| Thiết kế chiến lược (Strategy Design) | 14 / 15 |
| Chất lượng truy xuất (Retrieval Quality) | 9 / 10 (Recursive 9/10; best-per-query = 10/10) |
| Thuyết trình (Demo) | 4 / 5 (kịch bản + 3 insight đã soạn; chưa đứng lớp) |
| **Tổng phần nhóm** | **36 / 40** |
