# TXT to Excel + Thống kê Excel

Ứng dụng gồm 2 tab:

1. **Bóc tách TXT**: START/END, START → START tiếp theo → EOF, nhiều trường, nhiều dòng, regex, xuất Excel.
2. **Thống kê Excel**: upload `.xlsx/.xls`, chọn sheet và các cột dữ liệu để tạo thống kê.

## Tab Thống kê Excel

Chọn:
- Cột ngày/thời gian: bắt buộc.
- Cột lợi nhuận: bắt buộc.
- Cột nhóm/loại: tùy chọn, tạo biểu đồ tỷ lệ lợi nhuận theo nhóm.
- Cột doanh thu: tùy chọn.
- Cột chi phí: tùy chọn.

Ứng dụng tạo:
- Tổng lợi nhuận.
- Lợi nhuận trung bình.
- Số dòng và số dòng hợp lệ.
- Lợi nhuận theo tháng.
- Tăng trưởng lợi nhuận theo tháng.
- Lợi nhuận theo năm.
- Tăng trưởng lợi nhuận theo năm.
- Tỷ lệ lợi nhuận theo nhóm/loại.
- Doanh thu, chi phí và lợi nhuận theo tháng nếu các cột tương ứng được chọn.

## Chạy local

```bash
python -m venv venv
venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Mở `http://127.0.0.1:8000`.

## Render

Build Command:
`pip install -r requirements.txt`

Start Command:
`uvicorn app.main:app --host 0.0.0.0 --port $PORT`
