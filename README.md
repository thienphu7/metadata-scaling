# Metadata Scaling & Query Planning — Nhóm 7

**Thành viên & vai trò:** Nguyễn Thanh Phong (điều phối, research, README/slide) · Hùng (`gen.py`, S1–S2) · Phú (`optimize.py`, S3) · Đạt (`bench.py`, S4 held-out) · Vinh (`analysis/analyze.ipynb`)

## Problem
Khi một bảng lakehouse có nhiều file nhỏ và nhiều commit, engine phải đọc lại transaction log và thống kê min/max của từng file trước khi đọc dữ liệu. Phần *query planning* này có thể chiếm phần lớn thời gian truy vấn dù dữ liệu không lớn. Chi tiết: [docs/research.md](docs/research.md).

## Hypothesis
Với cùng 1 triệu dòng, thời gian planning tăng theo **số file và số commit trong log**, không theo dung lượng dữ liệu. Checkpoint log kết hợp sắp xếp dữ liệu theo cột lọc giảm p95 planning time **≥ 3 lần** ở quy mô lớn.

## Setup
- **Dữ liệu:** 1.000.000 dòng (`id`, `customer_id` 0–99.999, `amount` 0–1000), seed 42, thứ tự ngẫu nhiên. Cùng dữ liệu logic cho mọi state.
- **States** (20 file mỗi commit):

  | State | Số file | Số commit | Vai trò |
  |---|---|---|---|
  | S1 | 100 | 5 | dev |
  | S2 | 1.000 | 50 | dev |
  | S3 | 10.000 | 500 | dev |
  | S4 | 20.000 | 1.000 | **held-out** |

- **Truy vấn:** `q_main` `customer_id BETWEEN 1000 AND 1050`; `q_alt` `amount BETWEEN 100 AND 101` (cột không sort); `q_empty` `customer_id BETWEEN -100 AND -1` (0 dòng).
- **Thư viện:** Python 3.12, `deltalake==1.6.6`, `pyarrow==25.0.1` (đầy đủ trong `requirements.txt`).
- **Phần cứng** (cột `hardware` trong CSV):

  | State | Máy |
  |---|---|
  | S1, S2 | _TODO (Hùng)_ |
  | S3 | _TODO (Phú)_ |
  | S4 | _TODO (Đạt)_ |

- **Đo:** `n_runs = 10` mỗi tổ hợp state × variant × query × mode. `cold` = mỗi lần một process mới; `warm` = cùng process, bỏ 1 lần khởi động.

## Baseline
`baseline`: bảng như khi sinh ra, auto-checkpoint bị tắt (kiểm tra bằng `has_checkpoint`).

## Method
- `opt_a_checkpoint`: chỉ tạo checkpoint (gộp log thành 1 file Parquet), không đụng dữ liệu.
- `opt_b_sorted`: ghi lại dữ liệu sắp xếp theo `customer_id`, giữ nguyên số file, rồi checkpoint.

Chi phí tối ưu (từ `results/costs_S4.csv`):

| Variant | wall_time_s | bytes_rewritten |
|---|---|---|
| opt_a_checkpoint | _TODO_ | _TODO_ |
| opt_b_sorted | _TODO_ | _TODO_ |

## Metric
`PlanningSpeedup = p95(t_plan, baseline) / p95(t_plan, biến thể)`, cùng dữ liệu, cùng truy vấn, cùng số dòng kết quả, cùng máy.

`t_plan` là **proxy**: `t_plan = t_load + t_prune`, với `t_load` = `DeltaTable(path)` + `get_add_actions()` (replay log), `t_prune` = lọc file bằng min/max. `t_scan` (đọc file được chọn) đo riêng, không nằm trong metric.

## Result (S4 held-out)
_TODO: điền từ Vinh sau phút 85. Chỉ dùng số từ `results/results_S4.csv`._

| Query | Mode | p95 t_plan baseline (s) | p95 opt_a (s) | Speedup opt_a | p95 opt_b (s) | Speedup opt_b | files_selected base → opt_b |
|---|---|---|---|---|---|---|---|
| q_main | cold | | | | | | |
| q_main | warm | | | | | | |
| q_alt | cold | | | | | | |
| q_empty | cold | | | | | | |

Biểu đồ 1: _TODO_ p95 `t_plan` theo số file (S1→S4), mỗi biến thể một đường.
Biểu đồ 2: _TODO_ `files_selected` / `n_files_total` theo biến thể × truy vấn.

Kết luận giả thuyết: _TODO — chấp nhận / bác bỏ ngưỡng ≥ 3×, nêu rõ ở mode nào._

## Failure case
_TODO (có số liệu)._ Dự kiến: `q_alt` lọc theo `amount` (không sort) → `opt_b_sorted` vẫn chọn gần hết file, lợi ích chỉ còn phần checkpoint, trong khi đã trả chi phí rewrite toàn bộ dữ liệu.

## Limitations
- Không xóa được page cache của hệ điều hành; `cold` chỉ là process mới.
- Đĩa cục bộ, không phải object storage (S3) — độ trễ liệt kê/đọc log khác hẳn.
- Các state chạy trên máy khác nhau → chỉ so sánh trong cùng một state, không so tuyệt đối giữa state.
- `t_plan` đo bằng delta-rs + pyarrow, không phải planner của Spark/Trino.
- Chỉ lọc một cột; chưa thử ghi đồng thời trong lúc tối ưu; không chạy `vacuum`.

## Reproduce
```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/make_mock.py                     # MOCK tables + results_fake.csv
for S in S1 S2 S3 S4; do
  python src/gen.py --state $S && python src/optimize.py --state $S && python src/bench.py --state $S
done
python src/check_results.py                 # rows == expected_rows, schema, hardware
jupyter notebook analysis/analyze.ipynb
```

## References (truy cập 2026-10-04)
- Delta Lake Transaction Log Protocol — https://github.com/delta-io/delta/blob/master/PROTOCOL.md
- Delta Lake docs, Optimizations — https://docs.delta.io/latest/optimizations-oss.html
- [R2] Apache Iceberg, Maintenance — https://iceberg.apache.org/docs/nightly/maintenance/
- Apache Iceberg Table Spec — https://iceberg.apache.org/spec/
- [R10] Prammer et al., *Towards Functional Decomposition of Storage Formats*, CIDR 2025 — https://www.vldb.org/cidrdb/2025/towards-functional-decomposition-of-storage-formats.html
