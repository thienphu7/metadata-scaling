**BẢN XEM TRƯỚC TỪ DỮ LIỆU GIẢ — KHÔNG TRÍCH DẪN LÀM KẾT QUẢ.**

- Ở S4 (cold), opt_b_sorted đạt PlanningSpeedup 7.50× cho q_main; speedup tổng thời gian là 58.43×.
- Failure case q_alt trên cột không được sort: PlanningSpeedup của opt_b_sorted tại S4 là 7.30×; giá trị gần 1× nghĩa là lợi ích planning không đáng kể.
- Ở S1 với q_empty (cold), checkpoint đạt PlanningSpeedup 3.10×; cần đọc cùng thời gian tuyệt đối trước khi gọi đây là cải thiện thực dụng.
- Với baseline q_main tại S4, mean t_scan lớn gấp 9.44× mean t_plan; nếu tỷ lệ này lớn, tối ưu riêng planning ít tác động tới độ trễ đầu-cuối.
- Chưa tính được PaybackQueries của opt_b tại S4 vì thiếu chi phí thật hoặc biến thể không tiết kiệm planning time.