import io
import json
import re
from datetime import datetime
from typing import Any

import pandas as pd
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from .parser import parse_text

app = FastAPI(title="TXT to Excel + Analytics")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def read_txt(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1258", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def json_safe(v: Any):
    if pd.isna(v):
        return None
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.strftime("%Y-%m-%d")
    if hasattr(v, "item"):
        return v.item()
    return v


def numeric_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    def conv(x):
        if pd.isna(x):
            return None
        s = re.sub(r"[^\d,.\-]", "", str(x))
        if not s:
            return None
        try:
            if "," in s and "." in s:
                if s.rfind(",") > s.rfind("."):
                    s = s.replace(".", "").replace(",", ".")
                else:
                    s = s.replace(",", "")
            elif "." in s and s.count(".") > 1:
                s = s.replace(".", "")
            elif "," in s and s.count(",") > 1:
                s = s.replace(",", "")
            elif "," in s:
                a, b = s.rsplit(",", 1)
                s = a.replace(",", "") + ("." + b if len(b) <= 2 else b)
            return float(s)
        except Exception:
            return None
    return series.map(conv)


def date_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", dayfirst=True)


def aggregate_time(df: pd.DataFrame, date_col: str, value_col: str, freq: str):
    d = df[[date_col, value_col]].copy()
    d[date_col] = date_series(d[date_col])
    d[value_col] = numeric_series(d[value_col])
    d = d.dropna(subset=[date_col, value_col])
    if d.empty:
        return []
    d["period"] = d[date_col].dt.to_period(freq)
    grouped = d.groupby("period")[value_col].sum().sort_index()
    return [{"period": str(k), "value": float(v)} for k, v in grouped.items()]


def growth_from_series(points):
    result = []
    previous = None
    for p in points:
        growth = None if previous in (None, 0) else (p["value"] - previous) / abs(previous) * 100
        result.append({**p, "growth": None if growth is None else round(growth, 2)})
        previous = p["value"]
    return result


def excel_columns(data: bytes, filename: str):
    try:
        xls = pd.ExcelFile(io.BytesIO(data))
        sheets = xls.sheet_names
        frames = {sheet: pd.read_excel(xls, sheet_name=sheet) for sheet in sheets}
        return sheets, frames, None
    except Exception as e:
        return [], {}, f"Không đọc được Excel: {e}"


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/preview")
async def preview(file: UploadFile = File(...), config: str = Form(...)):
    if not file.filename or not file.filename.lower().endswith(".txt"):
        return {"ok": False, "errors": ["Chỉ hỗ trợ file .txt"]}
    try:
        cfg = json.loads(config)
    except Exception:
        return {"ok": False, "errors": ["Cấu hình không hợp lệ."]}
    rows, errors, blocks = parse_text(read_txt(await file.read()), cfg)
    return {"ok": True, "total_blocks": len(blocks), "preview": rows[:100], "errors": errors[:200]}


@app.post("/api/export")
async def export_excel(file: UploadFile = File(...), config: str = Form(...)):
    if not file.filename or not file.filename.lower().endswith(".txt"):
        return {"ok": False, "errors": ["Chỉ hỗ trợ file .txt"]}
    try:
        cfg = json.loads(config)
    except Exception:
        return {"ok": False, "errors": ["Cấu hình không hợp lệ."]}
    rows, errors, _ = parse_text(read_txt(await file.read()), cfg)
    df = pd.DataFrame(rows)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Dữ liệu")
        if errors:
            pd.DataFrame({"Lỗi/Cảnh báo": errors}).to_excel(writer, index=False, sheet_name="Lỗi")
    output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": 'attachment; filename="du_lieu_trich_xuat.xlsx"'})


@app.post("/api/excel/info")
async def excel_info(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        return {"ok": False, "errors": ["Hãy chọn file Excel .xlsx hoặc .xls"]}
    data = await file.read()
    sheets, frames, error = excel_columns(data, file.filename)
    if error:
        return {"ok": False, "errors": [error]}
    result = []
    for sheet, df in frames.items():
        result.append({
            "sheet": sheet,
            "rows": int(len(df)),
            "columns": [str(c) for c in df.columns],
            "preview": [{str(k): json_safe(v) for k, v in row.items()} for row in df.head(10).to_dict(orient="records")],
        })
    return {"ok": True, "sheets": result}


@app.post("/api/excel/analyze")
async def excel_analyze(
    file: UploadFile = File(...),
    sheet: str = Form(...),
    date_col: str = Form(...),
    profit_col: str = Form(...),
    category_col: str = Form(""),
    revenue_col: str = Form(""),
    cost_col: str = Form(""),
):
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        return {"ok": False, "errors": ["Hãy chọn file Excel .xlsx hoặc .xls"]}
    data = await file.read()
    _, frames, error = excel_columns(data, file.filename)
    if error or sheet not in frames:
        return {"ok": False, "errors": [error or "Không tìm thấy sheet."]}
    df = frames[sheet].copy()
    missing = [c for c in [date_col, profit_col] if c not in df.columns]
    if missing:
        return {"ok": False, "errors": [f"Không tìm thấy cột: {', '.join(missing)}"]}

    df[date_col] = date_series(df[date_col])
    df[profit_col] = numeric_series(df[profit_col])
    valid = df.dropna(subset=[date_col, profit_col]).copy()

    monthly = aggregate_time(df, date_col, profit_col, "M")
    annual = aggregate_time(df, date_col, profit_col, "Y")
    monthly_growth = growth_from_series(monthly)
    annual_growth = growth_from_series(annual)

    result = {
        "ok": True,
        "rows": int(len(df)),
        "valid_rows": int(len(valid)),
        "total_profit": float(valid[profit_col].sum()) if not valid.empty else 0,
        "average_profit": float(valid[profit_col].mean()) if not valid.empty else 0,
        "monthly": monthly,
        "monthly_growth": monthly_growth,
        "annual": annual,
        "annual_growth": annual_growth,
        "category": [],
        "revenue": [],
        "cost": [],
        "errors": [],
    }

    if category_col and category_col in df.columns:
        cat = df.assign(_value=numeric_series(df[profit_col])).groupby(category_col)["_value"].sum().dropna().sort_values(ascending=False).head(10)
        result["category"] = [{"name": str(k), "value": float(v)} for k, v in cat.items()]

    if revenue_col and revenue_col in df.columns:
        rev = df.assign(_value=numeric_series(df[revenue_col]))
        result["revenue"] = aggregate_time(rev, date_col, "_value", "M")

    if cost_col and cost_col in df.columns:
        cost = df.assign(_value=numeric_series(df[cost_col]))
        result["cost"] = aggregate_time(cost, date_col, "_value", "M")

    # Basic quality checks
    if len(valid) < len(df):
        result["errors"].append(f"Có {len(df) - len(valid)} dòng không có ngày hoặc lợi nhuận hợp lệ và đã được bỏ qua khi thống kê.")
    if not monthly:
        result["errors"].append("Không tạo được dữ liệu theo tháng. Hãy kiểm tra cột ngày và cột lợi nhuận.")
    return result
