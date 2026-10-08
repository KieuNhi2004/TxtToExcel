# TXT → Excel Extractor

Ứng dụng web Python + FastAPI để:

1. Người dùng tải file `.txt`.
2. Khai báo dấu hiệu bắt đầu và kết thúc của từng cụm.
3. Khai báo các trường cần bóc tách.
4. Xem trước dữ liệu.
5. Xuất thành file Excel `.xlsx`.

## Cài đặt

Khuyến nghị Python 3.10+.

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

Cài thư viện:

```bash
pip install -r requirements.txt
```

## Chạy

```bash
uvicorn app.main:app --reload
```

Mở trình duyệt:

```text
http://127.0.0.1:8000
```

## Các kiểu bóc tách

### 1. Lấy sau từ khóa

Ví dụ:

```text
Ngày: 12/03/2026
```

Từ khóa:

```text
Ngày:
```

Kết quả:

```text
12/03/2026
```

### 2. Lấy giữa 2 từ khóa

Ví dụ:

```text
Tên: Nguyễn Văn A
Mã: GD001
```

Bắt đầu:

```text
Tên:
```

Kết thúc:

```text
Mã:
```

Kết quả:

```text
Nguyễn Văn A
```

### 3. Regex

Ví dụ:

```text
Ngày: 12/03/2026
```

Regex:

```regex
Ngày:\s*(\d{2}/\d{2}/\d{4})
```

### 4. Kiểu Date

Các định dạng phổ biến được hỗ trợ:

```text
12/03/2026
12-03-2026
2026-03-12
12/03/2026 14:30
```

### 5. Kiểu Number

Có hỗ trợ các dạng như:

```text
1.500.000
2,000
1500000
```

## Luồng xử lý

```text
START
  ↓
Cụm dữ liệu
  ↓
END
  ↓
Cụm tiếp theo
```

Mỗi record chỉ được bóc tách bên trong chính cụm START → END đó, tránh lấy nhầm dữ liệu của record khác.
