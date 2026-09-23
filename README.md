# Bản tin tổng hợp tự động (6h – 12h – 21h)

Mỗi ngày 3 lần, hệ thống đọc các trang trong `sources.txt`, dùng Claude viết bản tóm tắt
tiếng Việt, rồi gửi vào **Email** và/hoặc **Zalo** của bạn. Chạy miễn phí trên GitHub Actions,
không cần bật máy tính.

## Cài đặt (làm một lần)

### 1. Khai báo các trang cần theo dõi
Sửa file `sources.txt`, mỗi dòng một địa chỉ. Nên dùng link RSS nếu trang có.

### 2. Thêm Secrets trên GitHub
Vào repo → **Settings → Secrets and variables → Actions → New repository secret**, thêm:

| Tên secret | Giá trị |
|---|---|
| `ANTHROPIC_API_KEY` | Khóa API từ https://console.anthropic.com (không có thì bản tin chỉ liệt kê tiêu đề) |
| `SMTP_USER` | Địa chỉ Gmail dùng để gửi, ví dụ `ban@gmail.com` |
| `SMTP_PASSWORD` | **Mật khẩu ứng dụng** Gmail (Tài khoản Google → Bảo mật → Xác minh 2 bước → Mật khẩu ứng dụng) |
| `EMAIL_TO` | Email nhận bản tin (nhiều email cách nhau bằng dấu phẩy) |
| `ZALO_BOT_TOKEN` | Token của Zalo Bot (xem bước 3) |
| `ZALO_CHAT_ID` | ID cuộc trò chuyện giữa bạn và bot (xem bước 3) |

Chỉ cần cấu hình Email **hoặc** Zalo; cấu hình cả hai thì gửi cả hai.

### 3. (Tùy chọn) Tạo Zalo Bot
1. Mở Zalo, tìm **"Zalo Bot Manager"** → tạo bot mới → nhận **Bot Token**.
2. Nhắn một tin bất kỳ cho bot của bạn.
3. Lấy `chat_id` bằng cách mở trình duyệt:
   `https://bot-api.zaloplatforms.com/bot<BOT_TOKEN>/getUpdates`
   và tìm trường `chat.id` trong kết quả.

### 4. Chạy thử
Vào tab **Actions → Bản tin tổng hợp → Run workflow**. Sau khoảng 1–2 phút bạn sẽ nhận được bản tin.

## Lịch chạy
Khai báo trong `.github/workflows/digest.yml` (giờ UTC, đã quy đổi sang giờ Việt Nam):
06:00, 12:00 và 21:00. Lưu ý: GitHub có thể chạy trễ vài phút đến ~15 phút vào giờ cao điểm,
và sẽ tạm dừng lịch chạy nếu repo không có hoạt động nào trong 60 ngày (vào tab Actions bấm bật lại).

## Chạy trên máy tính
```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...  SMTP_USER=...  SMTP_PASSWORD=...  EMAIL_TO=...
python digest.py
```
