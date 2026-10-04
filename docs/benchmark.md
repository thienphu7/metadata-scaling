# Benchmark — phần việc của Đạt

`src/bench.py` dùng nguyên `plan()` và `scan()` trong `src/common.py`.
Không thay đổi config, schema CSV hay thuật toán pruning của nhóm.

## Đầu vào và người bàn giao

| Bước | Cần đầu vào | Người cung cấp |
| --- | --- | --- |
| Chạy Python | Môi trường Python 3.12 đã chọn, đúng requirements | Đạt chọn môi trường; Phong chốt phiên bản |
| Thử MOCK | `common.py`, config, requirements, `make_mock.py` | Phong |
| Đo MOCK | Ba bảng MOCK và `results/state_MOCK.json` | Chạy `make_mock.py` cục bộ |
| Sinh S4 | `src/gen.py` có hỗ trợ S4 | Hùng |
| Tối ưu S4 | `src/optimize.py` | Phú |
| Đo S4 | Ba bảng S4 đã kiểm tra, `results/state_S4.json` | Đạt chạy generator và optimizer trên máy mình |

Không cần chờ CSV kết quả S1–S3 để viết benchmark. Phương pháp, số lần đo và
quy mô held-out phải được chốt với Phong trước khi xem kết quả S4.
Không tự thay đổi phương pháp để đạt speedup mục tiêu.

## Kiểm tra MOCK trước

Các lệnh dưới đây dùng `python` của môi trường đã được Đạt chọn; không tự tạo
môi trường hoặc cài dependency. Chạy từ thư mục gốc repo.

```sh
python -m unittest discover -s tests -v
python src/make_mock.py
python src/bench.py --state MOCK --check-only
python src/bench.py --state MOCK --runs 3
```

`make_mock.py` bổ sung `state_MOCK.json` đúng schema, tính `expected_rows` trực
tiếp từ 20.000 dòng dữ liệu logic trong bộ nhớ. Thời gian/bytes của baseline là
số đo thực. Script dừng nếu bảng MOCK đã tồn tại, tránh append lặp làm tăng số
dòng. Đây là bổ sung cho starter kit cần thông báo Phong khi bàn giao.
`results_fake.csv` chỉ dùng để phát triển notebook của Vinh, không làm đáp án
chuẩn hay kết quả thí nghiệm.

MOCK đầy đủ có 54 dòng: 3 biến thể × 3 truy vấn × 2 mode × 3 lần.
Kiểm tra số dòng kết quả đúng đáp án ở tất cả tổ hợp; `q_empty` trả về 0 dòng.
Không cần chỉnh pipeline theo số đo MOCK để đạt một speedup cụ thể.

## Chạy S4 sau khi nhận module

```sh
python src/gen.py --state S4
python src/optimize.py --state S4
python src/bench.py --state S4 --check-only
python src/bench.py --state S4
```

Chạy tuần tự trên máy Đạt; không chạy sinh bảng/tối ưu hay ứng dụng nặng đồng
thời với đo. Cắm sạc và ghi điều kiện máy vào ghi chú bàn giao. Mặc định S4 có
180 dòng đo (10 lần/tổ hợp), 90 process cold và 9 lượt warm-up bị bỏ. Không
tính thời gian sinh/tối ưu vào `t_plan` hoặc `t_scan`.

Ước lượng toàn bộ thời gian gồm sinh, copy/tối ưu, kiểm tra đúng dữ liệu, scan,
khởi động process và ghi CSV. Không chỉ dựa vào thời gian planning hoặc tốc
độ sinh file. ETA được in dần theo thời gian chạy thực của từng tổ hợp, gồm
khởi động process và ghi CSV; ETA chưa bao gồm warm-up nên chỉ là xấp xỉ.
Nếu dự kiến quá mốc phút 85, báo Phong trước khi xem kết quả held-out.

## Quy tắc đo và lỗi

- Cold: mỗi lần một process dùng đúng `sys.executable`; `--one STATE VARIANT
  QUERY` chỉ in một dòng JSON. Khởi động Python/import không nằm trong các
  timer của `common.py`. OS page cache vẫn có thể nóng, kể cả do bước kiểm tra.
- Warm: một lượt bỏ đi cho từng variant/query trước các lượt warm được ghi;
  mỗi lượt vẫn gọi `plan()` mới và mở lại DeltaTable.
- Đo cold trước, warm sau. Trong mỗi mode, vòng ngoài là run, vòng trong là
  variant × query theo thứ tự config hoặc CLI. So sánh biến thể trong cùng mode.
- `t_plan = t_load + t_prune`; `t_load` gồm mở bảng và lấy add-action stats;
  `t_prune` gồm lọc min/max và tạo danh sách đường dẫn.
- CSV giữ nguyên 14 cột trong hợp đồng. Mỗi dòng được flush và fsync ngoài
  khoảng thời gian đo, để giữ dữ liệu khi tiến trình bị ngắt.
- Sai `rows`: ghi dòng lỗi rồi cảnh báo đỏ và dừng. Báo nhóm; không tiếp tục
  hoặc để notebook coi đó là kết quả hợp lệ. Lỗi warm-up được in dạng JSON
  vào stderr, không đưa warm-up vào CSV đo.
- Sai checkpoint, thiếu đáp án chuẩn, thiếu bảng hoặc sai phiên bản package:
  dừng và nêu rõ đầu vào thiếu; không suy ra đáp án từ bảng cần kiểm tra.
- Kiểm tra số active file sau mỗi phép đo; không thay đổi bảng trong khi đo.

## Tiếp tục sau khi bị ngắt

```sh
python src/bench.py --state MOCK --runs 3 --resume
```

Phải dùng cùng state, số lần đo, tập/thứ tự variant và query, config, môi trường,
phần cứng và bảng. Chương trình chỉ append các khóa `(mode, variant, query,
run)` còn thiếu; không lặp khóa, không ghi đè dòng cũ. Nếu CSV chứa kết quả sai,
khóa trùng, bị hỏng hoặc session thay đổi thì dừng để người phụ trách xem xét.
Không tự resume hay chạy lại S4 để làm đẹp kết quả sau khi đóng băng.

File `results_<STATE>.benchmark.json` là nhật ký phương pháp, phiên bản Python/
package, hash mã nguồn benchmark/common và fingerprint metadata log dùng để
kiểm tra khi resume. Đây là file
bổ sung; tên và schema ba file bàn giao bắt buộc vẫn giữ nguyên. CSV bị khóa
trong lúc ghi bằng advisory lock POSIX (macOS/Linux).

## Bàn giao

1. `src/bench.py` đã thử MOCK cho Hùng và Phú trước mốc phút 45.
2. `results/results_S4.csv`, `results/costs_S4.csv`, `results/state_S4.json`
   cho Vinh; lưu thêm nhật ký phương pháp để kiểm tra tái lập.
3. Gửi Phong điều kiện máy, lần ngắt/lỗi nếu có và nhận xét độ ổn định từ số
   thật. Cold chỉ đảm bảo process mới; chưa xóa OS cache. Các state đo trên
   máy khác nhau không dùng thời gian tuyệt đối để kết luận scaling.

Chưa có kết quả thực thì không điền speedup, p95 hay kết luận giả thuyết.
