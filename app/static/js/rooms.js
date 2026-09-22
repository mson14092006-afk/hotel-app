/* rooms.js — Điều khiển trang "Edit room".
   Tải danh sách, thêm, sửa, xoá phòng bằng cách gọi API /api/rooms. */
(() => {
  "use strict";

  const API = "/api/rooms";
  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

  const els = {
    tbody: document.querySelector("#rooms-table tbody"),
    tableWrap: document.getElementById("table-wrap"),
    empty: document.getElementById("empty"),
    banner: document.getElementById("banner"),
    filters: document.getElementById("filters"),
    addBtn: document.getElementById("add-room"),
    dialog: document.getElementById("room-dialog"),
    dialogTitle: document.getElementById("dialog-title"),
    form: document.getElementById("room-form"),
    formBanner: document.getElementById("form-banner"),
    cancelBtn: document.getElementById("cancel-room"),
  };

  const roomsById = new Map(); // id -> room, để nút Sửa lấy dữ liệu không cần gọi lại API
  let editingId = null;        // null = đang thêm mới

  /* ---------- Tiện ích ---------- */

  /** Gọi API JSON, kèm CSRF token. Ném Error (có .fields) nếu server trả lỗi. */
  async function api(path, { method = "GET", body } = {}) {
    const response = await fetch(path, {
      method,
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      body: body ? JSON.stringify(body) : undefined,
    });

    if (response.status === 401) { // hết phiên đăng nhập
      window.location.assign("/login?next=/admin/rooms");
      throw new Error("Session expired.");
    }
    if (response.status === 204) return null;

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(data.error || `Request failed (${response.status}).`);
      error.fields = data.fields || {};
      throw error;
    }
    return data;
  }

  const capitalize = (text) => text.charAt(0).toUpperCase() + text.slice(1);

  function formatPrice(value) {
    return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 }).format(Number(value));
  }

  function showBanner(element, message, kind) {
    element.textContent = message;
    element.className = `banner banner-${kind}`;
    element.hidden = false;
  }

  /* ---------- Hiển thị danh sách ---------- */

  function cell(text, className) {
    const td = document.createElement("td");
    td.textContent = text; // textContent (không phải innerHTML) để chống XSS
    if (className) td.className = className;
    return td;
  }

  function actionButton(label, action, id, extraClass) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `btn ${extraClass}`.trim();
    button.textContent = label;
    button.dataset.action = action;
    button.dataset.id = id;
    return button;
  }

  function renderRooms(rooms, filtered) {
    roomsById.clear();
    els.tbody.replaceChildren();

    for (const room of rooms) {
      roomsById.set(room.id, room);
      const row = document.createElement("tr");

      const statusCell = document.createElement("td");
      const badge = document.createElement("span");
      badge.className = `badge badge-${room.status}`;
      badge.textContent = capitalize(room.status);
      statusCell.append(badge);

      const actionsCell = document.createElement("td");
      actionsCell.className = "actions";
      actionsCell.append(
        actionButton("Edit", "edit", room.id, ""),
        actionButton("Delete", "delete", room.id, "btn-danger"),
      );

      row.append(
        cell(room.id, "num"),
        cell(room.name),
        cell(capitalize(room.type)),
        cell(room.capacity, "num"),
        cell(room.total_units, "num"),
        cell(formatPrice(room.price_per_night), "num"),
        statusCell,
        actionsCell,
      );
      els.tbody.append(row);
    }

    els.tableWrap.hidden = rooms.length === 0;
    els.empty.hidden = rooms.length > 0;
    els.empty.textContent = filtered
      ? "No rooms match your filters."
      : "No rooms yet. Select \u201cAdd room\u201d to create the first one.";
  }

  async function loadRooms() {
    const params = new URLSearchParams();
    for (const [key, value] of new FormData(els.filters)) {
      const text = value.toString().trim();
      if (text) params.set(key, text);
    }
    try {
      const data = await api(`${API}?${params}`);
      renderRooms(data.items, params.toString() !== "");
    } catch (error) {
      showBanner(els.banner, error.message, "error");
    }
  }

  /* ---------- Hộp thoại thêm / sửa ---------- */

  function clearErrors() {
    els.formBanner.hidden = true;
    for (const p of els.form.querySelectorAll(".field-error")) p.textContent = "";
  }

  function openDialog(room) {
    editingId = room ? room.id : null;
    els.dialogTitle.textContent = room ? "Edit room" : "Add room";
    els.form.reset();
    clearErrors();

    if (room) {
      const f = els.form.elements;
      f["name"].value = room.name;
      f["type"].value = room.type;
      f["status"].value = room.status;
      f["capacity"].value = room.capacity;
      f["total_units"].value = room.total_units;
      f["price_per_night"].value = String(Number(room.price_per_night));
      f["description"].value = room.description || "";
    }
    els.dialog.showModal();
    els.form.elements["name"].focus();
  }

  function showFormErrors(error) {
    let general = error.fields._ ? error.fields._ : null;
    for (const [field, message] of Object.entries(error.fields)) {
      const target = els.form.querySelector(`[data-error-for="${field}"]`);
      if (target) target.textContent = message;
    }
    if (!general && !Object.keys(error.fields).length) general = error.message;
    if (general) showBanner(els.formBanner, general, "error");
  }

  els.form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearErrors();

    const f = els.form.elements;
    const payload = {
      name: f["name"].value,
      type: f["type"].value,
      status: f["status"].value,
      capacity: f["capacity"].value,
      total_units: f["total_units"].value,
      price_per_night: f["price_per_night"].value,
      description: f["description"].value,
    };

    const isEdit = editingId !== null;
    try {
      const saved = await api(isEdit ? `${API}/${editingId}` : API, {
        method: isEdit ? "PUT" : "POST",
        body: payload,
      });
      els.dialog.close();
      showBanner(els.banner, `Room \u201c${saved.name}\u201d ${isEdit ? "updated" : "created"}.`, "success");
      await loadRooms();
    } catch (error) {
      showFormErrors(error);
    }
  });

  /* ---------- Xoá ---------- */

  async function deleteRoom(room) {
    if (!window.confirm(`Delete room \u201c${room.name}\u201d? This cannot be undone.`)) return;
    try {
      await api(`${API}/${room.id}`, { method: "DELETE" });
      showBanner(els.banner, `Room \u201c${room.name}\u201d deleted.`, "success");
      await loadRooms();
    } catch (error) {
      showBanner(els.banner, error.message, "error");
    }
  }

  /* ---------- Gắn sự kiện ---------- */

  els.addBtn.addEventListener("click", () => openDialog(null));
  els.cancelBtn.addEventListener("click", () => els.dialog.close());

  // Một listener cho cả bảng (event delegation) thay vì một listener mỗi nút
  els.tbody.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const room = roomsById.get(Number(button.dataset.id));
    if (!room) return;
    if (button.dataset.action === "edit") openDialog(room);
    if (button.dataset.action === "delete") deleteRoom(room);
  });

  // Lọc: gõ tìm kiếm (debounce 250ms để không gọi API mỗi phím), đổi select thì lọc ngay
  let timer;
  els.filters.addEventListener("input", (event) => {
    clearTimeout(timer);
    timer = setTimeout(loadRooms, event.target.tagName === "SELECT" ? 0 : 250);
  });
  els.filters.addEventListener("submit", (event) => event.preventDefault());

  loadRooms();
})();
