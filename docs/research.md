# Research — Vì sao metadata làm chậm query planning

> Nháp của Phong. Mọi con số thực nghiệm sẽ lấy từ `results/` sau khi chạy; tài liệu này chỉ chứa lập luận và trích dẫn nguồn.

## 1. Vì sao metadata trở thành nút cổ chai
Bảng Delta là một thư mục file Parquet cộng với **transaction log** `_delta_log/`: mỗi commit là một file JSON chứa các action (`add`, `remove`, `metaData`, …). Bảng không có "danh sách file" sẵn — reader phải tự dựng lại: *"A given snapshot of the table can be computed by replaying the events committed to the table in ascending order by commit version"* [D1]. Vì vậy chi phí mở bảng (`t_load`) tỉ lệ với:
- **số commit** (số file JSON phải liệt kê, mở, parse), và
- **số `add` action** — mỗi data file là một dòng, kèm chuỗi JSON `stats` chứa `minValues`/`maxValues` [D1].

Dung lượng dữ liệu gần như không xuất hiện trong công thức này — đó là lý do thí nghiệm giữ cố định 1 triệu dòng và chỉ thay số file/commit.

Sau khi có danh sách file, engine **cắt tỉa (pruning)** bằng min/max: bỏ file nào có `[min, max]` không giao với điều kiện lọc. Nhưng nếu dữ liệu ghi theo thứ tự ngẫu nhiên, mỗi file đều trải gần hết miền giá trị → các khoảng min/max **chồng lấn**, gần như không file nào bị loại. Kết quả: vừa tốn công đọc metadata của N file, vừa không thu được lợi ích pruning.

## 2. Vì sao hai biến thể có thể giúp
- **Checkpoint (`opt_a_checkpoint`) → giảm `t_load`.** Checkpoint là file Parquet chứa *"the complete replay of all actions, up to and including the checkpointed table version"*; nó *"allow[s] readers to short-cut the cost of reading the log up-to a given point"*, và `_last_checkpoint` trỏ thẳng đến checkpoint mới nhất để khỏi liệt kê toàn bộ log [D1]. Reader đọc 1 file Parquet dạng cột thay vì parse hàng trăm/nghìn file JSON. Checkpoint **không** thay đổi số file hay min/max, nên không giúp pruning.
- **Sắp xếp theo cột lọc (`opt_b_sorted`) → giảm số file được chọn.** Khi ghi lại dữ liệu theo `customer_id`, mỗi file chiếm một khoảng hẹp, rời nhau → min/max loại được gần hết file với `q_main`. Delta docs mô tả cùng cơ chế cho Z-order: co-locality *"is automatically used by Delta Lake in data-skipping algorithms"* [D2]. Đổi lại: phải rewrite toàn bộ dữ liệu, và chỉ có lợi cho cột đã sort (`q_alt` theo `amount` dự kiến không cải thiện).
- **Liên hệ R10.** Prammer et al. lập luận rằng định dạng cột hiện dùng **cùng một ranh giới phân vùng** cho cả nén lẫn metadata bỏ qua dòng, trong khi *"no single horizontal partition size optimizes both"*; họ đề xuất tách *storage layer* khỏi *search acceleration layer* [R10]. Thí nghiệm của nhóm là một phiên bản ở mức bảng: số file (đơn vị lưu trữ) quyết định kích thước metadata, còn cách tổ chức min/max (cấu trúc tăng tốc tìm kiếm) quyết định hiệu quả pruning — hai thứ đang bị buộc chung, nên tối ưu cái này có thể làm hại cái kia.

## 3. So sánh với Apache Iceberg
Iceberg giải cùng bài toán bằng **cây metadata nhiều tầng** thay vì log tuyến tính: `metadata.json` → **manifest list** (mỗi snapshot) → **manifest** (Avro, mỗi dòng là một data file kèm `lower_bounds`/`upper_bounds`) → data file [I2]. Manifest list lưu thống kê partition của từng manifest, *"used to avoid reading manifests that are not required"* [I2] — tức pruning hai tầng, không phải replay lịch sử.

Nhưng vấn đề vẫn tồn tại ở dạng khác: *"More data files leads to more metadata stored in manifest files"* [R2]; snapshot tích lũy cần `expireSnapshots` *"to keep the size of table metadata small"* [R2]; và manifest được gom theo thứ tự ghi, chỉ nhanh *"when the write pattern aligns with read filters"* — nếu không thì phải `rewriteManifests` [R2]. Tương ứng: expire snapshot/rewrite manifest ≈ checkpoint (gọn metadata); compact/sort data ≈ `opt_b_sorted` (min/max hẹp).

## 4. Chưa kiểm thử & rủi ro production
- **Lọc nhiều cột:** sort một cột chỉ giúp cột đó; Z-order/Hilbert cho nhiều cột chưa được thử.
- **Object storage (S3/GCS):** thí nghiệm chạy trên đĩa cục bộ. Trên S3, mỗi file log là một request có độ trễ mạng và việc liệt kê `_delta_log` tốn hơn → lợi ích checkpoint có thể khác (nhiều khả năng lớn hơn), nhưng chưa đo.
- **Chi phí rewrite định kỳ:** `opt_b_sorted` ghi lại toàn bộ dữ liệu; với bảng nhận ghi liên tục, thứ tự sort bị phá dần và phải chạy lại → cần so chi phí (`costs_<STATE>.csv`) với lợi ích đọc.
- **Ghi đồng thời khi tối ưu:** rewrite + overwrite trong lúc có writer khác có thể gây xung đột commit; thí nghiệm chỉ chạy đơn luồng.
- **Phạm vi proxy:** `t_plan` đo bằng delta-rs + pyarrow, không phải planner của Spark/Trino; không xóa được page cache của hệ điều hành.
- **Không vacuum:** file cũ sau rewrite vẫn nằm trên đĩa; production cần vacuum/retention, chưa đánh giá.

## Tài liệu tham khảo (truy cập 2026-10-04)
- [D1] Delta Lake Transaction Log Protocol. https://github.com/delta-io/delta/blob/master/PROTOCOL.md
- [D2] Delta Lake docs — Optimizations (data skipping, Z-order, compaction). https://docs.delta.io/latest/optimizations-oss.html
- [R2] Apache Iceberg — Maintenance. https://iceberg.apache.org/docs/nightly/maintenance/
- [I2] Apache Iceberg — Table Spec (manifest list, manifests). https://iceberg.apache.org/spec/
- [R10] M. Prammer, X. Zeng, R. Meng, W. McKinney, H. Zhang, A. Pavlo, J. M. Patel. *Towards Functional Decomposition of Storage Formats.* CIDR 2025. https://www.vldb.org/cidrdb/2025/towards-functional-decomposition-of-storage-formats.html
