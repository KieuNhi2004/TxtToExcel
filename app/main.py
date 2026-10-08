from pathlib import Path
import io
import re
from datetime import datetime

import pandas as pd
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="TXT → Excel Extractor", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def home():
    return (TEMPLATE_DIR / "index.html").read_text(encoding="utf-8")


def split_blocks(text: str, start_marker: str, end_marker: str = ""):
    """
    Tách dữ liệu theo 2 chế độ:

    1. Có END: START -> dữ liệu -> END
    2. Không có END: START -> dữ liệu -> START tiếp theo;
       START cuối -> dữ liệu -> hết file.
    """
    if not start_marker:
        raise ValueError("Dấu hiệu bắt đầu không được để trống.")

    blocks = []
    start_positions = []
    pos = 0

    while True:
        start = text.find(start_marker, pos)
        if start == -1:
            break
        start_positions.append(start)
        pos = start + len(start_marker)

    if not start_positions:
        return blocks

    # Không có END: START tiếp theo là ranh giới của cụm hiện tại.
    if not end_marker:
        for i, start in enumerate(start_positions):
            next_start = start_positions[i + 1] if i + 1 < len(start_positions) else len(text)
            blocks.append({"text": text[start:next_start], "closed": True})
        return blocks

    # Có END: không cho phép tìm END vượt qua START kế tiếp.
    for i, start in enumerate(start_positions):
        content_start = start + len(start_marker)
        next_start = start_positions[i + 1] if i + 1 < len(start_positions) else len(text)
        end = text.find(end_marker, content_start, next_start)

        if end == -1:
            blocks.append({"text": text[start:next_start], "closed": False})
        else:
            blocks.append({"text": text[start:end + len(end_marker)], "closed": True})

    return blocks


def extract_after(block: str, marker: str) -> str:
    idx = block.find(marker)
    if idx == -1:
        return ""
    value = block[idx + len(marker):]
    return value.splitlines()[0].strip() if value.splitlines() else value.strip()


def extract_before(block: str, marker: str) -> str:
    idx = block.find(marker)
    if idx == -1:
        return ""
    lines = block[:idx].splitlines()
    return lines[-1].strip() if lines else block[:idx].strip()


def extract_between(block: str, start: str, end: str) -> str:
    a = block.find(start)
    if a == -1:
        return ""
    a += len(start)
    b = block.find(end, a)
    if b == -1:
        return block[a:].strip()
    return block[a:b].strip()


def extract_regex(block: str, pattern: str) -> str:
    try:
        m = re.search(pattern, block, flags=re.MULTILINE)
    except re.error:
        return ""
    if not m:
        return ""
    if m.lastindex:
        return m.group(1).strip()
    return m.group(0).strip()


def convert_value(value: str, data_type: str):
    value = value.strip()
    if not value:
        return ""

    if data_type == "date":
        formats = [
            "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d",
            "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
            "%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"
        ]
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                pass

        # Tự tìm ngày trong chuỗi nếu có tiền tố như "Ngày: 12/03/2026"
        m = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b", value)
        if m:
            raw = m.group(1).replace("-", "/")
            try:
                return datetime.strptime(raw, "%d/%m/%Y")
            except ValueError:
                pass
        return value

    if data_type == "number":
        cleaned = re.sub(r"[^\d,.\-]", "", value)
        if not cleaned:
            return ""
        # Hỗ trợ 1.500.000 và 1,500.50
        if cleaned.count(".") > 1 and "," not in cleaned:
            cleaned = cleaned.replace(".", "")
        elif "." in cleaned and "," in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            # 1,5 => decimal; 1,500 => thường là hàng nghìn
            parts = cleaned.split(",")
            if len(parts[-1]) == 3:
                cleaned = cleaned.replace(",", "")
            else:
                cleaned = cleaned.replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return value

    return value


def parse_fields(block: str, fields):
    result = {}
    for field in fields:
        name = field.get("name", "").strip()
        mode = field.get("mode", "after")
        data_type = field.get("type", "text")
        marker = field.get("marker", "")
        end_marker = field.get("end_marker", "")
        pattern = field.get("pattern", "")

        if not name:
            continue

        if mode == "after":
            value = extract_after(block, marker)
        elif mode == "before":
            value = extract_before(block, marker)
        elif mode == "between":
            value = extract_between(block, marker, end_marker)
        elif mode == "regex":
            value = extract_regex(block, pattern)
        elif mode == "line":
            value = extract_after(block, marker)
        else:
            value = ""

        result[name] = convert_value(value, data_type)

    return result


def process_text(text: str, start_marker: str, end_marker: str, fields):
    blocks = split_blocks(text, start_marker, end_marker)
    rows = []
    errors = []

    for index, block_info in enumerate(blocks, start=1):
        row = parse_fields(block_info["text"], fields)
        row["__STT__"] = index

        if not block_info["closed"]:
            errors.append(f"Cụm #{index}: không tìm thấy dấu hiệu kết thúc.")

        missing = [
            f.get("name", "")
            for f in fields
            if f.get("name", "").strip() and not row.get(f.get("name", "").strip())
        ]
        if missing:
            errors.append(
                f"Cụm #{index}: thiếu dữ liệu ở: {', '.join(missing)}"
            )

        rows.append(row)

    return rows, errors


@app.post("/api/preview")
async def preview(
    file: UploadFile = File(...),
    start_marker: str = Form(...),
    end_marker: str = Form(...),
    fields_json: str = Form(...)
):
    import json

    if not file.filename.lower().endswith(".txt"):
        raise HTTPException(400, "Chỉ hỗ trợ file .txt.")

    try:
        fields = json.loads(fields_json)
    except Exception:
        raise HTTPException(400, "Cấu hình trường không hợp lệ.")

    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("cp1258", errors="replace")

    rows, errors = process_text(text, start_marker, end_marker, fields)

    clean_rows = []
    for row in rows[:100]:
        clean = {k: (v.isoformat() if isinstance(v, datetime) else v)
                 for k, v in row.items() if k != "__STT__"}
        clean_rows.append(clean)

    return {
        "total": len(rows),
        "errors": errors[:100],
        "columns": [f["name"] for f in fields if f.get("name", "").strip()],
        "rows": clean_rows,
    }


@app.post("/api/export")
async def export_excel(
    file: UploadFile = File(...),
    start_marker: str = Form(...),
    end_marker: str = Form(...),
    fields_json: str = Form(...)
):
    import json

    if not file.filename.lower().endswith(".txt"):
        raise HTTPException(400, "Chỉ hỗ trợ file .txt.")

    try:
        fields = json.loads(fields_json)
    except Exception:
        raise HTTPException(400, "Cấu hình trường không hợp lệ.")

    raw = await file.read()
    for encoding in ("utf-8", "utf-8-sig", "cp1258", "cp1252"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            text = None
    if text is None:
        text = raw.decode("utf-8", errors="replace")

    rows, errors = process_text(text, start_marker, end_marker, fields)

    columns = [f["name"] for f in fields if f.get("name", "").strip()]
    data = [{col: row.get(col, "") for col in columns} for row in rows]
    df = pd.DataFrame(data, columns=columns)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="DuLieu")
        ws = writer.book["DuLieu"]
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

        for col_cells in ws.columns:
            max_len = 0
            col_letter = col_cells[0].column_letter
            for cell in col_cells:
                value = "" if cell.value is None else str(cell.value)
                max_len = max(max_len, len(value))
            ws.column_dimensions[col_letter].width = min(max(max_len + 2, 12), 40)

        # Định dạng ngày
        for idx, field in enumerate(fields, start=1):
            if field.get("type") == "date":
                for cell in ws.iter_cols(min_col=idx, max_col=idx, min_row=2):
                    for c in cell:
                        if isinstance(c.value, datetime):
                            c.number_format = "dd/mm/yyyy"

    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="ket_qua.xlsx"'
        },
    )
