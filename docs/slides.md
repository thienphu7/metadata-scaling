# Slide outline — Nhóm 7 (4 slide)

> Ô `_TODO_` chỉ điền bằng số từ `results/` sau phút 85. Không dùng số đo thử trong bối cảnh nhóm.

## Slide 1 — Pain + giả thuyết
- **Tiêu đề:** Cùng 1 triệu dòng, 100 file và 20.000 file khác nhau thế nào?
- Hình: sơ đồ `_delta_log/` — 5 file JSON (S1) vs 1.000 file JSON (S4) → mở bảng = replay toàn bộ log.
- Min/max của file chồng lấn (thứ tự ngẫu nhiên) → pruning không loại được file.
- **Giả thuyết:** planning tăng theo số file/commit, không theo dữ liệu; checkpoint + sort giảm p95 `t_plan` ≥ 3× ở quy mô lớn.

## Slide 2 — Thiết kế thí nghiệm
- Bảng state: S1 100 / S2 1.000 / S3 10.000 file (dev), **S4 20.000 file (held-out, chốt phương pháp trước khi chạy)**.
- Biến thể: `baseline` · `opt_a_checkpoint` (gộp log) · `opt_b_sorted` (sort `customer_id` + checkpoint, giữ số file).
- Truy vấn: `q_main` (cột đã sort) · `q_alt` (cột không sort — failure case dự kiến) · `q_empty` (0 dòng, planning thuần).
- Đo: `t_plan = t_load + t_prune` (proxy), 10 lần, `cold` (process mới) / `warm`; kiểm tra `rows == expected_rows`.

## Slide 3 — Kết quả
- Biểu đồ 1: p95 `t_plan` theo số file, 3 đường biến thể (log scale). _TODO_
- Bảng S4: p95 baseline / opt_a / opt_b, PlanningSpeedup, chi phí (`wall_time_s`, `bytes_rewritten`). _TODO_
- Một câu kết luận: giả thuyết ≥ 3× đúng/sai ở mode nào. _TODO_

## Slide 4 — Quyết định
- **Nên triển khai:** _TODO_ (dự kiến: checkpoint gần như miễn phí → luôn bật; sort chỉ khi truy vấn chủ yếu lọc theo một cột).
- **Khi nào không đáng:** `q_alt` — số liệu _TODO_; chi phí rewrite định kỳ khi dữ liệu ghi liên tục.
- **Rủi ro còn lại:** object storage (S3), lọc nhiều cột, ghi đồng thời khi tối ưu, không xóa OS cache.
- **Thử tiếp:** Z-order nhiều cột; đo trên S3/MinIO; tần suất checkpoint tối ưu; so với Iceberg `rewriteManifests`.
