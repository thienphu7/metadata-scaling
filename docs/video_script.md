# Kịch bản video — Nhóm 7 (giọng đọc Gemini TTS)

> Lời thoại trùng với speaker notes trong deck. Ô `[__]` và `[... / ...]` chỉ điền bằng số thật từ `results/` sau phút 85 — điền xong mới tạo giọng đọc cho slide 4 và 5.
> Thuật ngữ đã viết sẵn theo cách đọc (ví dụ "p chín mươi lăm" thay cho "p95") để TTS không đọc sai.

## Prompt phong cách cho Gemini TTS
Dán trước mỗi đoạn lời thoại:

```
Đọc đoạn sau bằng tiếng Việt, giọng miền Bắc, tốc độ vừa phải, rõ ràng,
phong cách thuyết trình kỹ thuật thân thiện. Ngắt nhẹ ở dấu phẩy, ngắt dài hơn ở dấu chấm.
Giữ nguyên các thuật ngữ tiếng Anh: Delta, transaction log, checkpoint, Parquet,
planning, baseline, held-out, customer id, cold, warm, Z-order, S3.
```

Mỗi slide tạo một file âm thanh riêng: `audio/01_cover.wav` … `audio/05_decision.wav`.

## Slide 1 — Bìa (`01_cover`)
Xin chào, chúng tôi là Nhóm 7. Đề tài của nhóm là Metadata Scaling và Query Planning. Khi metadata của một bảng lakehouse phình to, engine có thể tốn nhiều thời gian để lên kế hoạch truy vấn, thậm chí hơn cả thời gian đọc dữ liệu. Trong vài phút tới, chúng tôi sẽ trình bày vấn đề, cách thiết kế thí nghiệm, kết quả trên tập held-out, và quyết định của nhóm.

## Slide 2 — Vấn đề + giả thuyết (`02_pain`)
Một bảng Delta gồm các file Parquet, cộng với một transaction log. Mỗi lần mở bảng, engine phải đọc lại toàn bộ log để biết bảng gồm những file nào, kèm thống kê min và max của từng file. Với cùng một triệu dòng, nếu chia thành một trăm file thì log chỉ có năm commit. Nhưng nếu chia thành hai mươi nghìn file, log có một nghìn commit và hai mươi nghìn bản ghi file. Thêm vào đó, dữ liệu được ghi theo thứ tự ngẫu nhiên, nên khoảng min max của các file chồng lấn lên nhau, và việc lọc bằng min max gần như không loại được file nào. Giả thuyết của nhóm là: thời gian planning tăng theo số file và số commit, chứ không theo dung lượng dữ liệu. Và checkpoint kết hợp sắp xếp dữ liệu theo cột lọc sẽ giảm p chín mươi lăm của planning ít nhất ba lần ở quy mô lớn.

## Slide 3 — Thiết kế thí nghiệm (`03_design`)
Nhóm giữ cố định một triệu dòng dữ liệu với cùng một seed, và chỉ thay đổi cách chia file: từ một trăm file đến hai mươi nghìn file. Trạng thái lớn nhất, S bốn, được giữ lại làm tập held-out: mọi phương pháp được chốt trước khi chạy nó. Nhóm so sánh ba biến thể. Baseline giữ nguyên bảng như khi sinh ra. Biến thể A chỉ tạo checkpoint, tức gộp log thành một file Parquet. Biến thể B sắp xếp lại dữ liệu theo customer id, giữ nguyên số file, rồi checkpoint. Có ba truy vấn: truy vấn chính lọc theo cột đã sắp xếp, truy vấn phụ lọc theo cột amount không được sắp xếp, và một truy vấn trả về không dòng để đo planning thuần. Mỗi tổ hợp chạy mười lần, ở cả chế độ cold và warm, và số dòng trả về luôn phải khớp với kết quả kỳ vọng.

## Slide 4 — Kết quả S4 (`04_results`) — CHỜ SỐ LIỆU
Trên trạng thái held-out S bốn, với hai mươi nghìn file, p chín mươi lăm planning time của baseline là [__] giây. Chỉ với checkpoint, con số này giảm còn [__] giây, tức nhanh hơn [__] lần. Khi kết hợp thêm sắp xếp dữ liệu, p chín mươi lăm còn [__] giây, nhanh hơn [__] lần, với chi phí tối ưu một lần là [__] giây. Như vậy, giả thuyết ngưỡng ba lần [được xác nhận / không được xác nhận] ở chế độ [cold / warm].

## Slide 5 — Quyết định (`05_decision`) — CHỜ SỐ LIỆU
Kết luận của nhóm: [checkpoint nên / không nên được bật ...], vì [lý do từ số liệu]. Sắp xếp dữ liệu chỉ đáng làm khi truy vấn chủ yếu lọc theo đúng cột đã sắp xếp. Failure case rõ nhất là truy vấn phụ: lọc theo cột amount không được sắp xếp, biến thể B vẫn chọn [__] trên hai mươi nghìn file, nên không hơn checkpoint đơn thuần, mà vẫn phải trả chi phí ghi lại dữ liệu. Những gì nhóm chưa kiểm thử gồm: object storage như S3, lọc trên nhiều cột, và ghi đồng thời trong lúc tối ưu. Bước tiếp theo là thử Z-order nhiều cột và đo trên S3. Cảm ơn mọi người đã lắng nghe.

## Ghép video
1. Xuất deck ra PDF, đổi từng trang thành PNG 1920×1080: `slides/01.png` … `slides/05.png` (cùng thứ tự với file âm thanh).
2. Ghép mỗi slide với âm thanh của nó, rồi nối lại (cần `ffmpeg`):

```bash
for i in 01 02 03 04 05; do
  a=$(ls audio/${i}_*.wav)
  ffmpeg -y -loop 1 -i slides/$i.png -i "$a" -c:v libx264 -tune stillimage -pix_fmt yuv420p \
         -c:a aac -b:a 192k -shortest seg_$i.mp4
done
printf "file 'seg_%s.mp4'\n" 01 02 03 04 05 > list.txt
ffmpeg -y -f concat -safe 0 -i list.txt -c copy nhom7_metadata_scaling.mp4
```
