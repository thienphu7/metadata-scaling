# Kịch bản video — Nhóm 7 (giọng đọc Gemini TTS)

> Khoảng 1,5–2 phút. Lời thoại trùng với speaker notes trong deck. Ô `[__]` chỉ điền bằng số thật từ `results/` sau phút 85.

## Prompt cho Gemini TTS
```
Đọc bằng tiếng Việt, giọng miền Bắc, tốc độ vừa phải, rõ ràng, phong cách thuyết trình kỹ thuật.
Giữ nguyên thuật ngữ tiếng Anh: Delta, transaction log, checkpoint, planning, baseline, held-out, customer id, cold, warm, S3.
```
Mỗi slide một file âm thanh: `audio/01_cover.wav` … `audio/05_decision.wav`.

## 1. Bìa (`01_cover`)
Xin chào, chúng tôi là Nhóm 7. Câu hỏi của nhóm: khi metadata của bảng lakehouse phình to, thời gian lên kế hoạch truy vấn tăng thế nào, và làm sao giảm nó?

## 2. Vấn đề + giả thuyết (`02_pain`)
Mỗi lần mở một bảng Delta, engine phải đọc lại toàn bộ transaction log để biết bảng có những file nào. Cùng một triệu dòng, một trăm file chỉ cần năm commit, còn hai mươi nghìn file cần một nghìn commit. Dữ liệu lại xếp ngẫu nhiên, nên thống kê min max gần như không loại được file nào. Giả thuyết: planning tăng theo số file và số commit, và checkpoint cộng sắp xếp dữ liệu giảm p chín mươi lăm ít nhất ba lần.

## 3. Thiết kế thí nghiệm (`03_design`)
Nhóm giữ cố định một triệu dòng, chỉ thay số file, từ một trăm đến hai mươi nghìn. Trạng thái lớn nhất, S bốn, là held-out, chỉ chạy sau khi đã chốt phương pháp. Ba biến thể: baseline, chỉ checkpoint, và sắp xếp theo customer id rồi checkpoint. Ba truy vấn: lọc theo cột đã sắp xếp, lọc theo cột không sắp xếp, và một truy vấn rỗng để đo planning thuần. Mỗi tổ hợp chạy mười lần, cả cold và warm.

## 4. Kết quả S4 (`04_results`) — CHỜ SỐ LIỆU
Trên S bốn, p chín mươi lăm planning của baseline là [__] giây. Checkpoint đưa xuống [__] giây, nhanh hơn [__] lần. Thêm sắp xếp: [__] giây, nhanh hơn [__] lần, với chi phí [__] giây. Giả thuyết ba lần [được / không được] xác nhận.

## 5. Quyết định (`05_decision`) — CHỜ SỐ LIỆU
Kết luận: [checkpoint nên / không nên bật], vì [lý do từ số liệu]. Sắp xếp chỉ đáng khi truy vấn lọc đúng cột đã sắp xếp. Với cột amount không được sắp xếp, biến thể B vẫn chọn [__] trên hai mươi nghìn file, tức tốn công ghi lại mà không được gì thêm. Chưa kiểm thử: S3, lọc nhiều cột, và ghi đồng thời. Cảm ơn mọi người đã lắng nghe.

## Ghép video
Xuất deck ra PDF → PNG 1920×1080 `slides/01.png` … `slides/05.png`, rồi:

```bash
for i in 01 02 03 04 05; do
  ffmpeg -y -loop 1 -i slides/$i.png -i audio/${i}_*.wav -c:v libx264 -tune stillimage \
         -pix_fmt yuv420p -c:a aac -b:a 192k -shortest seg_$i.mp4
done
printf "file 'seg_%s.mp4'\n" 01 02 03 04 05 > list.txt
ffmpeg -y -f concat -safe 0 -i list.txt -c copy nhom7_metadata_scaling.mp4
```
