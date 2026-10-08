let fieldId = 0;

function addField(defaults = {}) {
    fieldId++;

    const wrapper = document.createElement("div");
    wrapper.className = "field";
    wrapper.dataset.id = fieldId;

    wrapper.innerHTML = `
        <div class="field-grid">
            <div>
                <label>Tên cột Excel</label>
                <input type="text" class="field-name" placeholder="Ví dụ: Thời gian"
                       value="${escapeHtml(defaults.name || "")}">
            </div>

            <div>
                <label>Cách lấy</label>
                <select class="field-mode" onchange="toggleExtra(this)">
                    <option value="after">Lấy sau từ khóa</option>
                    <option value="before">Lấy trước từ khóa</option>
                    <option value="between">Lấy giữa 2 từ khóa</option>
                    <option value="regex">Regex</option>
                </select>
            </div>

            <div>
                <label>Kiểu dữ liệu</label>
                <select class="field-type">
                    <option value="text">Text</option>
                    <option value="date">Date</option>
                    <option value="number">Number</option>
                </select>
            </div>

            <div>
                <label>Từ khóa / Regex</label>
                <input type="text" class="field-marker"
                       placeholder="Ví dụ: Ngày:"
                       value="${escapeHtml(defaults.marker || "")}">
            </div>
        </div>

        <div class="field-extra">
            <label class="end-label">Từ khóa kết thúc</label>
            <input type="text" class="field-end-marker"
                   placeholder="Chỉ dùng cho 'giữa 2 từ khóa'">

            <label class="regex-label">Regex</label>
            <input type="text" class="field-pattern"
                   placeholder="Ví dụ: Ngày:\\s*(\\d{2}/\\d{2}/\\d{4})">

            <button type="button" class="danger" onclick="this.closest('.field').remove()">
                Xóa trường
            </button>
        </div>
    `;

    document.getElementById("fields").appendChild(wrapper);

    if (defaults.mode) {
        wrapper.querySelector(".field-mode").value = defaults.mode;
    }
    if (defaults.type) {
        wrapper.querySelector(".field-type").value = defaults.type;
    }
    wrapper.querySelector(".field-end-marker").value = defaults.end_marker || "";
    wrapper.querySelector(".field-pattern").value = defaults.pattern || "";

    toggleExtra(wrapper.querySelector(".field-mode"));
}

function toggleExtra(select) {
    const field = select.closest(".field");
    const mode = select.value;

    field.querySelector(".end-label").style.display =
        mode === "between" ? "block" : "none";
    field.querySelector(".field-end-marker").style.display =
        mode === "between" ? "block" : "none";

    field.querySelector(".regex-label").style.display =
        mode === "regex" ? "block" : "none";
    field.querySelector(".field-pattern").style.display =
        mode === "regex" ? "block" : "none";
}

function getFields() {
    return [...document.querySelectorAll(".field")].map(field => ({
        name: field.querySelector(".field-name").value.trim(),
        mode: field.querySelector(".field-mode").value,
        type: field.querySelector(".field-type").value,
        marker: field.querySelector(".field-marker").value,
        end_marker: field.querySelector(".field-end-marker").value,
        pattern: field.querySelector(".field-pattern").value
    })).filter(x => x.name);
}

function getFormData() {
    const file = document.getElementById("file").files[0];
    if (!file) throw new Error("Bạn chưa chọn file TXT.");

    const startMarker = document.getElementById("startMarker").value;
    const endMarker = document.getElementById("endMarker").value;
    const fields = getFields();

    if (!startMarker) throw new Error("Chưa nhập dấu hiệu bắt đầu.");
    if (!endMarker) throw new Error("Chưa nhập dấu hiệu kết thúc.");
    if (!fields.length) throw new Error("Bạn chưa thêm trường cần bóc tách.");

    const fd = new FormData();
    fd.append("file", file);
    fd.append("start_marker", startMarker);
    fd.append("end_marker", endMarker);
    fd.append("fields_json", JSON.stringify(fields));

    return fd;
}

async function preview() {
    try {
        showStatus("Đang phân tích file...");
        const response = await fetch("/api/preview", {
            method: "POST",
            body: getFormData()
        });

        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Có lỗi xảy ra.");

        renderPreview(data);
        showStatus(`Đã tìm thấy ${data.total} cụm dữ liệu.`);
    } catch (e) {
        showStatus(e.message, true);
    }
}

async function exportExcel() {
    try {
        showStatus("Đang tạo file Excel...");

        const response = await fetch("/api/export", {
            method: "POST",
            body: getFormData()
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || "Không thể xuất Excel.");
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);

        const a = document.createElement("a");
        a.href = url;
        a.download = "ket_qua.xlsx";
        document.body.appendChild(a);
        a.click();
        a.remove();

        URL.revokeObjectURL(url);
        showStatus("Xuất Excel thành công.");
    } catch (e) {
        showStatus(e.message, true);
    }
}

function renderPreview(data) {
    document.getElementById("previewSection").classList.remove("hidden");
    document.getElementById("count").textContent =
        `${data.total} cụm — hiển thị tối đa 100 dòng`;

    const table = document.getElementById("previewTable");
    table.innerHTML = "";

    const head = document.createElement("tr");
    data.columns.forEach(col => {
        const th = document.createElement("th");
        th.textContent = col;
        head.appendChild(th);
    });
    table.appendChild(head);

    data.rows.forEach(row => {
        const tr = document.createElement("tr");
        data.columns.forEach(col => {
            const td = document.createElement("td");
            td.textContent = row[col] ?? "";
            tr.appendChild(td);
        });
        table.appendChild(tr);
    });

    const errors = document.getElementById("errors");
    errors.innerHTML = "";

    if (!data.errors.length) {
        errors.innerHTML = "<li>Không có cảnh báo.</li>";
    } else {
        data.errors.forEach(err => {
            const li = document.createElement("li");
            li.className = "error";
            li.textContent = err;
            errors.appendChild(li);
        });
    }
}

function showStatus(message, error = false) {
    const el = document.getElementById("status");
    el.classList.remove("hidden");
    el.textContent = message;
    el.style.color = error ? "#b42318" : "#222";
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

document.getElementById("file").addEventListener("change", function() {
    document.getElementById("fileName").textContent =
        this.files[0] ? this.files[0].name : "Chưa chọn file";
});

// Mặc định một số trường mẫu
addField({
    name: "Thời gian",
    mode: "after",
    type: "date",
    marker: "Ngày:"
});
addField({
    name: "Mã giao dịch",
    mode: "after",
    type: "text",
    marker: "Mã giao dịch:"
});
