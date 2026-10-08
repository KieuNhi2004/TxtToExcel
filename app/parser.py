import re
from datetime import datetime
from typing import Any


def split_blocks(text: str, start_marker: str, end_marker: str | None = None):
    if not start_marker:
        raise ValueError("Chưa nhập dấu bắt đầu.")
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if start_marker in line]
    blocks, warnings = [], []
    if not starts:
        return [], ["Không tìm thấy dấu bắt đầu trong file."]

    if end_marker:
        for idx, start in enumerate(starts):
            next_start = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
            end = next((j for j in range(start + 1, next_start) if end_marker in lines[j]), None)
            if end is None:
                warnings.append(f"Khối {idx + 1}: không tìm thấy dấu kết thúc.")
                end = next_start - 1
            blocks.append("\n".join(lines[start:end + 1]).strip())
    else:
        for idx, start in enumerate(starts):
            end = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
            blocks.append("\n".join(lines[start:end]).strip())
    return blocks, warnings


def _line_value_after(lines: list[str], marker: str):
    for i, line in enumerate(lines):
        if marker in line:
            rest = line.split(marker, 1)[1].strip()
            if rest:
                return rest, i
            for j in range(i + 1, len(lines)):
                if lines[j].strip():
                    return lines[j].strip(), j
            return "", i
    return "", -1


def _multiline_after(block: str, marker: str, other_markers: list[str]):
    pos = block.find(marker)
    if pos < 0:
        return "", -1
    after = block[pos + len(marker):]
    if after.startswith("\r\n"):
        after = after[2:]
    elif after.startswith(("\n", "\r")):
        after = after[1:]
    candidates = [p for m in other_markers if m and m != marker for p in [after.find(m)] if p >= 0]
    if candidates:
        after = after[:min(candidates)]
    return after.strip(), pos


def _between(block: str, start_marker: str, end_marker: str):
    if not start_marker or not end_marker:
        return "", -1
    s = block.find(start_marker)
    if s < 0:
        return "", -1
    s += len(start_marker)
    e = block.find(end_marker, s)
    return (block[s:].strip(), s) if e < 0 else (block[s:e].strip(), s)


def _before(block: str, marker: str):
    pos = block.find(marker)
    return (block[:pos].rstrip(), pos) if pos >= 0 else ("", -1)


def _regex(block: str, pattern: str):
    if not pattern:
        return "", -1
    m = re.search(pattern, block, re.MULTILINE | re.DOTALL)
    if not m:
        return "", -1
    return ((m.group(1) if m.groups() else m.group(0)).strip(), m.start())


def convert_value(value: str, data_type: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if data_type == "text":
        return value
    if data_type == "date":
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                pass
        return value
    if data_type == "number":
        s = re.sub(r"[^\d,.\-]", "", value)
        if not s:
            return ""
        try:
            if "," not in s:
                if s.count(".") > 1:
                    s = s.replace(".", "")
                elif s.count(".") == 1:
                    left, right = s.split(".")
                    if len(right) == 3:
                        s = left + right
            elif "." in s:
                if s.rfind(",") > s.rfind("."):
                    s = s.replace(".", "").replace(",", ".")
                else:
                    s = s.replace(",", "")
            else:
                left, right = s.rsplit(",", 1)
                s = left.replace(",", "") + ("." + right if len(right) <= 2 else right)
            return float(s) if "." in s else int(s)
        except ValueError:
            return value
    return value


def extract_field(block: str, field: dict, all_markers: list[str]):
    mode = field.get("mode", "after")
    marker = field.get("marker", "")
    if mode == "after":
        value, pos = (_multiline_after(block, marker, all_markers) if field.get("scope") == "multiline" else _line_value_after(block.splitlines(), marker))
    elif mode == "between":
        value, pos = _between(block, marker, field.get("end_marker", ""))
    elif mode == "before":
        value, pos = _before(block, marker)
    elif mode == "regex":
        value, pos = _regex(block, field.get("regex", ""))
    else:
        return "", False, "Kiểu lấy dữ liệu không hợp lệ."
    if pos < 0:
        return "", False, f"Không tìm thấy: {marker or field.get('regex', '')}"
    return convert_value(value, field.get("data_type", "text")), True, ""


def parse_text(text: str, config: dict):
    blocks, split_warnings = split_blocks(
        text,
        config.get("start_marker", ""),
        None if config.get("no_end_marker") else (config.get("end_marker") or None),
    )
    fields = config.get("fields", [])
    all_markers = [f.get("marker", "") for f in fields if f.get("marker")]
    rows, errors = [], list(split_warnings)
    for block_index, block in enumerate(blocks, start=1):
        row, row_errors = {}, []
        for field in fields:
            name = field.get("name", "").strip()
            if not name:
                continue
            value, ok, error = extract_field(block, field, all_markers)
            row[name] = value
            if not ok:
                row_errors.append(f"{name}: {error}")
        if row_errors:
            errors.append(f"Khối {block_index}: " + " | ".join(row_errors))
        rows.append(row)
    return rows, errors, blocks
