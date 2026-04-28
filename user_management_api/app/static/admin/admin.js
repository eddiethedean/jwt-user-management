async function jsonFetch(url, options = {}) {
  const csrfMeta = document.querySelector('meta[name="csrf-token"]');
  const csrfToken = csrfMeta ? csrfMeta.getAttribute("content") : "";
  const resp = await fetch(url, {
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
      ...(options.headers || {}),
    },
    ...options,
  });
  const text = await resp.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (!resp.ok) {
    const msg =
      (data && (data.detail || data.error)) || text || `HTTP ${resp.status}`;
    throw new Error(msg);
  }
  return data;
}

function getBasePath() {
  const m = document.querySelector('meta[name="base-path"]');
  const raw = m ? String(m.getAttribute("content") || "") : "";
  if (!raw) return "";
  return raw.endsWith("/") ? raw.slice(0, -1) : raw;
}

function withBase(path) {
  const bp = getBasePath();
  if (!bp) return path;
  if (!path) return bp;
  if (path.startsWith("/")) return `${bp}${path}`;
  return `${bp}/${path}`;
}

function byId(id) {
  return document.getElementById(id);
}

function setHidden(el, hidden) {
  if (!el) return;
  el.classList.toggle("hidden", hidden);
}

function asText(v) {
  if (v === null || v === undefined) return "";
  return String(v);
}

function appendCell(tr, value) {
  const td = document.createElement("td");
  td.textContent = asText(value);
  tr.appendChild(td);
}

function renderUsers(rows) {
  const tbody = document.querySelector("#usersTable tbody");
  if (!tbody) return;
  tbody.replaceChildren();
  for (const u of rows) {
    const tr = document.createElement("tr");
    appendCell(tr, u.id);
    appendCell(tr, u.email);
    appendCell(tr, u.full_name);
    appendCell(tr, u.is_active);
    appendCell(tr, u.is_admin);
    appendCell(tr, u.email_verified);
    appendCell(tr, Array.isArray(u.permissions) ? u.permissions.join(",") : "");
    appendCell(tr, u.created_at);
    tbody.appendChild(tr);
  }
}

async function loadUsers() {
  const err = byId("usersError");
  setHidden(err, true);
  try {
    const data = await jsonFetch(withBase("/admin/api/users"));
    renderUsers(Array.isArray(data) ? data : []);
  } catch (e) {
    if (err) {
      err.textContent = e.message || "Failed to load users";
      setHidden(err, false);
    }
  }
}

async function wireInviteForm() {
  const form = byId("inviteForm");
  if (!form) return;
  const msg = byId("inviteMsg");

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (msg) setHidden(msg, true);

    const fd = new FormData(form);
    const email = String(fd.get("email") || "").trim();
    const full_name = String(fd.get("full_name") || "").trim() || null;
    const is_admin = fd.get("is_admin") === "on";
    const permissions = String(fd.get("permissions") || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    try {
      const data = await jsonFetch(withBase("/admin/api/invites"), {
        method: "POST",
        body: JSON.stringify({ email, full_name, is_admin, permissions }),
      });
      if (msg) {
        msg.textContent = `Invite sent: ${data.invite_url || ""}`;
        msg.classList.remove("error");
        setHidden(msg, false);
      }
      form.reset();
    } catch (e) {
      if (msg) {
        msg.textContent = e.message || "Invite failed";
        msg.classList.add("error");
        setHidden(msg, false);
      }
    }
  });
}

async function logout() {
  try {
    await jsonFetch(withBase("/admin/logout"), { method: "POST", body: "{}" });
  } finally {
    window.location.assign(withBase("/admin/login"));
  }
}

function main() {
  const logoutBtn = byId("logoutBtn");
  if (logoutBtn) logoutBtn.addEventListener("click", logout);
  const refresh = byId("refreshUsersBtn");
  if (refresh) refresh.addEventListener("click", loadUsers);
  wireInviteForm();
  loadUsers();
}

document.addEventListener("DOMContentLoaded", main);

