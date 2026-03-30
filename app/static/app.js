async function api(url, method = "GET", body = null) {
  const opts = { method, headers: {} };
  if (body) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

function getPublishedAtISO() {
  const v = document.getElementById("publishedAt").value;
  return v || null;
}

function payloadFromForm() {
  return {
    title: document.getElementById("title").value,
    content: document.getElementById("content").value,
    published_at: getPublishedAtISO(),
  };
}

function escapeHtml(s) {
  return (s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setStatus(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text || "";
}

function fillSelect(selectEl, values, selectedValue = null) {
  if (!selectEl) return;
  selectEl.innerHTML = (values || [])
    .map((v) => {
      const sel = v === selectedValue ? "selected" : "";
      return `<option value="${escapeHtml(v)}" ${sel}>${escapeHtml(v)}</option>`;
    })
    .join("");
}

let __posts = [];
let __activeId = null;

async function loadCategories() {
  const res = await api("/api/categories");
  const cats = res.categories || [];
  window.__CATEGORIES__ = cats;

  const sel = document.getElementById("finalCategory");
  fillSelect(sel, cats, cats[0] ?? null);
}

function filterAndSortPosts(posts) {
  const q = (document.getElementById("q").value || "").toLowerCase().trim();
  const sort = document.getElementById("sort").value;

  let out = posts;
  if (q) {
    out = out.filter((p) => {
      const t = (p.title || "").toLowerCase();
      const pred = (p.predicted_category || "").toLowerCase();
      const fin = (p.final_category || "").toLowerCase();
      return t.includes(q) || pred.includes(q) || fin.includes(q);
    });
  }

  return [...out].sort((a, b) => (sort === "oldest" ? a.id - b.id : b.id - a.id));
}

function renderPostsList(posts) {
  const el = document.getElementById("postsList");
  const items = filterAndSortPosts(posts || []);

  if (items.length === 0) {
    el.innerHTML = `<div class="empty">Žádné články.</div>`;
    return;
  }

  el.innerHTML = items
    .map((p) => {
      const active = p.id === __activeId ? "list-item--active" : "";
      const title = escapeHtml((p.title || "(bez titulku)").slice(0, 120));
      const meta = `#${p.id} • ${escapeHtml(p.final_category || "-")} • pred: ${escapeHtml(p.predicted_category || "-")}`;
      return `
        <button class="list-item ${active}" data-id="${p.id}">
          <div class="list-item__title">${title}</div>
          <div class="list-item__meta">${meta}</div>
        </button>
      `;
    })
    .join("");

  for (const btn of el.querySelectorAll(".list-item")) {
    btn.addEventListener("click", () => {
      __activeId = Number(btn.getAttribute("data-id"));
      renderPostsList(__posts);
      renderDetail(__activeId);
    });
  }
}

function buildCategorySelect(current) {
  const cats = window.__CATEGORIES__ || [];
  const options = cats
    .map((c) => {
      const sel = c === current ? "selected" : "";
      return `<option value="${escapeHtml(c)}" ${sel}>${escapeHtml(c)}</option>`;
    })
    .join("");
  return `<select id="detailFinalCategory" class="select">${options}</select>`;
}

function renderDetail(id) {
  const el = document.getElementById("detail");
  const p = __posts.find((x) => x.id === id);

  if (!p) {
    el.textContent = "Vyber článek…";
    return;
  }

  el.innerHTML = `
    <article class="article">
      <h3 class="article__title">${escapeHtml(p.title || "(bez titulku)")}</h3>

      <div class="article__bar">
        <span class="tag">pred: ${escapeHtml(p.predicted_category || "-")}</span>
        <span class="tag">final: ${escapeHtml(p.final_category || "-")}</span>
        ${buildCategorySelect(p.final_category)}
        <button class="btn btn--small" id="btnUpdateCategory">Uložit</button>
        <span id="updateOut"></span>
      </div>

      <pre class="content">${escapeHtml(p.content || "")}</pre>
    </article>
  `;

  document.getElementById("btnUpdateCategory").addEventListener("click", async () => {
    const out = document.getElementById("updateOut");
    out.textContent = "…";
    try {
      const val = document.getElementById("detailFinalCategory").value;
      await api(`/api/posts/${p.id}`, "PATCH", { final_category: val });
      out.textContent = "OK";
      await reloadPosts(true);
    } catch (e) {
      out.textContent = "ERR";
    }
  });
}

async function reloadPosts(keepSelection = false) {
  const { posts } = await api("/api/posts");
  __posts = posts || [];

  if (!keepSelection) __activeId = __posts?.[0]?.id ?? null;
  if (__activeId && !__posts.some((p) => p.id === __activeId)) __activeId = __posts?.[0]?.id ?? null;

  renderPostsList(__posts);
  if (__activeId) renderDetail(__activeId);
  else document.getElementById("detail").textContent = "Vyber článek…";
}

document.getElementById("btnPredict").addEventListener("click", async () => {
  setStatus("predOut", "…");
  try {
    const res = await api("/api/predict", "POST", payloadFromForm());
    setStatus("predOut", res.predicted_category);

    const sel = document.getElementById("finalCategory");
    if (sel && window.__CATEGORIES__?.includes(res.predicted_category)) {
      sel.value = res.predicted_category;
    }

    window.__predicted = res.predicted_category;
  } catch (e) {
    setStatus("predOut", "ERR");
  }
});

document.getElementById("btnSave").addEventListener("click", async () => {
  setStatus("saveOut", "…");
  try {
    const payload = payloadFromForm();
    payload.predicted_category = window.__predicted || null;

    const sel = document.getElementById("finalCategory");
    payload.final_category = sel ? sel.value : null;

    const res = await api("/api/posts", "POST", payload);
    setStatus("saveOut", `#${res.id}`);

    document.getElementById("title").value = "";
    document.getElementById("content").value = "";

    await reloadPosts(true);
    __activeId = res.id;
    renderPostsList(__posts);
    renderDetail(__activeId);
  } catch (e) {
    setStatus("saveOut", "ERR");
  }
});

document.getElementById("btnReload").addEventListener("click", async () => {
  await reloadPosts(true);
});

document.getElementById("q").addEventListener("input", () => renderPostsList(__posts));
document.getElementById("sort").addEventListener("change", () => renderPostsList(__posts));

(async () => {
  try {
    await loadCategories();
  } catch (e) {
    window.__CATEGORIES__ = [];
  }
  await reloadPosts(false);
})().catch(() => {});