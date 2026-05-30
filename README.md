# 📡 FB Monitor Bot

Bot Telegram theo dõi trạng thái public của tài khoản Facebook.
Tự động thông báo khi profile đổi từ **LIVE → DIE** hoặc ngược lại.

---

## 📁 Cấu trúc

```
fb_monitor_bot/
├── bot.py           # Bot chính
├── checker.py       # Logic check Facebook
├── database.py      # SQLite operations
├── config.py        # Cấu hình
├── requirements.txt
└── fb-monitor.service  # Systemd service
```

---

## 🚀 Deploy lên VPS (Ubuntu)

### 1. Tạo Bot Telegram

1. Nhắn tin cho [@BotFather](https://t.me/BotFather) trên Telegram
2. Gõ `/newbot` → đặt tên → lấy **BOT_TOKEN**

### 2. Upload code lên VPS

```bash
# Trên máy local
scp -r fb_monitor_bot/ user@your-vps-ip:/opt/fb_monitor_bot
```

Hoặc dùng git:
```bash
# Trên VPS
git clone <your-repo> /opt/fb_monitor_bot
```

### 3. Cài đặt môi trường

```bash
cd /opt/fb_monitor_bot

# Tạo virtual environment
python3 -m venv venv
source venv/bin/activate

# Cài thư viện
pip install -r requirements.txt
```

### 4. Cấu hình

Chỉnh file `config.py`:
```python
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"   # ← Điền token của bạn
ADMIN_IDS = [123456789]              # ← Telegram ID của bạn (tùy chọn)
CHECK_INTERVAL = 60                  # ← Giây (60 = 1 phút)
```

Hoặc dùng biến môi trường:
```bash
export BOT_TOKEN="YOUR_TOKEN"
export CHECK_INTERVAL="60"
```

### 5. Chạy thử

```bash
source venv/bin/activate
python bot.py
```

### 6. Chạy nền với systemd (khuyên dùng)

```bash
# Copy service file
sudo cp fb-monitor.service /etc/systemd/system/

# Sửa token trong service file
sudo nano /etc/systemd/system/fb-monitor.service
# → Thay YOUR_BOT_TOKEN_HERE bằng token thật
# → Thay User=ubuntu nếu user VPS khác

# Kích hoạt
sudo systemctl daemon-reload
sudo systemctl enable fb-monitor
sudo systemctl start fb-monitor

# Kiểm tra status
sudo systemctl status fb-monitor

# Xem log
journalctl -u fb-monitor -f
```

---

## 📖 Hướng dẫn sử dụng

| Lệnh | Mô tả |
|------|-------|
| `/add <id>` | Thêm Facebook ID vào theo dõi |
| `/remove <id>` | Xóa khỏi danh sách |
| `/list` | Xem danh sách đang theo dõi |
| `/check <id>` | Kiểm tra ngay một ID |
| `/checkall` | Kiểm tra tất cả ngay |
| `/status` | Thống kê tổng quan |

### Ví dụ thêm ID:
```
/add 100012345678
/add zuck
/add https://facebook.com/zuck
```

---

## ⚙️ Cơ chế hoạt động

- Bot gọi URL `https://www.facebook.com/{id}` không cần đăng nhập
- Phân tích HTTP status code và nội dung trang
- Nếu thấy các dấu hiệu "trang không tồn tại" → **DIE**
- Nếu trang tải bình thường → **LIVE**
- Khi trạng thái thay đổi → gửi thông báo Telegram ngay lập tức

---

## ⚠️ Lưu ý

- Bot chỉ check **public profile** — không đăng nhập, không vi phạm ToS
- Facebook đôi khi chặn request → bot sẽ trả về `unknown` thay vì sai
- Nên để `CHECK_INTERVAL` tối thiểu 60 giây để tránh bị rate limit
