# Bàn giao benchmark S4 — Đạt

## Kết quả đã tạo

- `results/results_S4.csv`: 180 dòng đo, 3 variant × 3 query × 2 mode × 10 run.
- `results/state_S4.json`: 1.000.000 dòng, 20.000 file, 1.000 commit ghi dữ liệu;
  baseline không có checkpoint. Đáp án chuẩn: q_main = 473, q_alt = 1030,
  q_empty = 0.
- `results/costs_S4.csv`: hai dòng chi phí tối ưu; cả hai giữ nguyên 20.000 file.
- `results/validation_S4.json`: kiểm tra đầy đủ và thống kê planning từ toàn bộ
  10 mẫu/tổ hợp; p95 dùng nội suy tuyến tính của NumPy.
- `results/S4_protocol.json` và `results/results_S4.benchmark.json`: cấu hình,
  phiên bản môi trường, hash nguồn và metadata dùng kiểm tra phương pháp.
- `results/benchmark_logs/`: log tests, tạo MOCK/S4, tối ưu, benchmark và kiểm tra.

Môi trường: conda `vin_lab`, Python 3.12.14, đúng mọi phiên bản trong
`requirements.txt`; `pip check` không tìm thấy dependency hỏng.
Hardware: `Macbook-Pro-Gaohonggg.local|macOS-26.6.2-arm64-arm-64bit|cpu=12`.

## Kiểm tra

9 tests thành công. MOCK có đủ 54 lượt đo (3 lần/tổ hợp) và đáp án tính độc lập
từ 20.000 dòng dữ liệu logic. S4 có đủ 180 khóa duy nhất, đúng schema, không
sai số dòng, không thiếu tổ hợp; q_empty chọn 0 file và trả về 0 dòng.
`src/check_results.py` báo OK. Hash nguồn/config và fingerprint log bảng giữ
nguyên từ lúc chốt phương pháp đến hết đo; không loại bỏ hay chạy lại lượt nào.

## Số liệu nhanh cho Phong và Vinh

| q_main | p95 planning baseline (s) | opt_a (s) | speedup opt_a | opt_b (s) | speedup opt_b |
| --- | ---: | ---: | ---: | ---: | ---: |
| cold | 0.398969 | 0.158342 | 2.520× | 0.156118 | 2.556× |
| warm | 0.229506 | 0.021542 | 10.654× | 0.020103 | 11.416× |

`q_main`: baseline/opt_a chọn 8.184 file; opt_b chọn 10 file.
`q_alt`: baseline/opt_a chọn 19.876 file; opt_b chọn 19.888 file.
Sort không cải thiện pruning cho truy vấn lọc `amount` trong lần thử này.

Checkpoint mất 0.483239 s, không rewrite dữ liệu. Sort + rewrite + checkpoint
mất 8.752749 s, rewrite 37.505.786 byte. Sinh baseline mất 218.023658 s;
thời gian này và chi phí copy không nằm trong thời gian planning.

Ghi chú bàn giao: CV mẫu của planning trong 18 tổ hợp S4 không quá 7,01%; mọi
lượt đo được giữ lại, không có sai lệch kết quả truy vấn. Ngưỡng speedup ≥3×
cho q_main đạt ở warm nhưng chưa đạt ở cold. Cold chỉ đảm bảo process Python
mới, không xóa OS page cache; không có xác nhận rằng các ứng dụng nền đã đóng
hoặc máy đang cắm sạc, nên không ghi các điều kiện đó như sự thật.

## Phạm vi

Trong lượt thực thi này không sửa `gen.py`, `optimize.py`, `common.py`, config,
requirements hay notebook/README của thành viên khác. Không cần đồng đội chạy
S4 thêm; các file bàn giao đã được tạo cục bộ trên cùng máy cho cả ba variant.
S1–S3 trong repo ghi hardware Windows; phân tích không gộp thời gian tuyệt đối
của các máy khác nhau để kết luận scaling.
