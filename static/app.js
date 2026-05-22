"use strict";

const state = { etf: null, etfs: [], maxWeight: 0, view: "portfolio" };

const $ = (sel) => document.querySelector(sel);
const statusEl = $("#status");

function setStatus(msg, isError = false) {
  statusEl.textContent = msg || "";
  statusEl.classList.toggle("error", !!isError);
}

function fmtInt(n) {
  return Number(n).toLocaleString("en-US");
}
function fmtPct(n) {
  return Number(n).toFixed(2) + "%";
}
function deltaCell(n, pct = false) {
  const cls = n > 0 ? "up" : n < 0 ? "down" : "";
  const sign = n > 0 ? "+" : n < 0 ? "−" : "";
  const val = pct ? Math.abs(n).toFixed(2) + "%" : fmtInt(Math.abs(n));
  return `<span class="${cls}">${sign}${val}</span>`;
}
const esc = (s) =>
  String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// ---- Theme toggle ----
function initTheme() {
  const saved = localStorage.getItem("etf-theme");
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const theme = saved || (prefersDark ? "dark" : "light");
  document.documentElement.setAttribute("data-theme", theme);
  $("#themeToggle").onclick = () => {
    const next =
      document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("etf-theme", next);
  };
}

// ---- Skeleton ----
function showSkeleton() {
  const tbody = $("#portfolioTable tbody");
  const widths = ["30%", "55%", "70%", "45%"];
  tbody.innerHTML = Array.from({ length: 8 })
    .map(
      () =>
        `<tr class="skeleton">${Array.from({ length: 5 })
          .map(
            (_, i) =>
              `<td><div class="bar" style="width:${i === 0 ? "40%" : widths[(i + 1) % 4]}"></div></td>`
          )
          .join("")}</tr>`
    )
    .join("");
}

// ---- ETF tabs ----
async function initEtfs() {
  state.etfs = await (await fetch("/api/etfs")).json();
  const tabs = $("#etfTabs");
  tabs.innerHTML = "";
  state.etfs.forEach((code, i) => {
    const b = document.createElement("button");
    b.className = "etf-tab" + (i === 0 ? " active" : "");
    b.textContent = code;
    b.setAttribute("role", "tab");
    b.setAttribute("aria-selected", i === 0 ? "true" : "false");
    b.onclick = () => selectEtf(code);
    tabs.appendChild(b);
  });
  state.etf = state.etfs[0];
}

function selectEtf(code) {
  state.etf = code;
  document.querySelectorAll(".etf-tab").forEach((t) => {
    const on = t.textContent === code;
    t.classList.toggle("active", on);
    t.setAttribute("aria-selected", on ? "true" : "false");
  });
  loadLatest();
}

// ---- Portfolio ----
async function loadPortfolio(dateStr) {
  setStatus("讀取中…");
  showSkeleton();
  const url = "/api/portfolio?etf=" + state.etf + (dateStr ? "&date=" + dateStr : "");
  let data;
  try {
    data = await (await fetch(url)).json();
  } catch (e) {
    setStatus("連線失敗，請稍後再試", true);
    $("#portfolioTable tbody").innerHTML = "";
    return null;
  }
  if (data.error) {
    setStatus(data.error, true);
    $("#portfolioTable tbody").innerHTML = "";
    return null;
  }
  renderPortfolio(data);
  renderKpis(data);
  setStatus(data.cached ? "資料來自本地快取" : "");
  return data;
}

function renderKpis(data) {
  const kpi = $("#kpiSection");
  const holdings = data.holdings || [];
  if (!holdings.length) {
    kpi.classList.add("hidden");
    return;
  }
  const top = holdings.reduce((a, b) => (b.weight > a.weight ? b : a), holdings[0]);
  const top10 = [...holdings].sort((a, b) => b.weight - a.weight).slice(0, 10);
  const top10Weight = top10.reduce((s, h) => s + h.weight, 0);

  const cards = [
    { label: "持股檔數", value: holdings.length, sub: data.tran_date || "" },
    { label: "最大持股", value: esc(top.name), sub: `${esc(top.code)}　${fmtPct(top.weight)}` },
    { label: "前十大權重", value: fmtPct(top10Weight), sub: "Top 10 集中度" },
  ];
  kpi.innerHTML = cards
    .map(
      (c) =>
        `<div class="kpi"><div class="kpi-label">${c.label}</div>` +
        `<div class="kpi-value">${c.value}</div>` +
        `<div class="kpi-sub">${c.sub}</div></div>`
    )
    .join("");
  kpi.classList.remove("hidden");
}

function renderPortfolio(data) {
  const tbody = $("#portfolioTable tbody");
  tbody.innerHTML = "";
  $("#portfolioMeta").textContent = data.tran_date
    ? `${data.tran_date}　共 ${data.holdings.length} 檔`
    : "";

  if (!data.holdings || !data.holdings.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="empty">${esc(
      data.message || "查無資料"
    )}</td></tr>`;
    return;
  }
  if (data.tran_date) $("#dateInput").value = data.tran_date;

  const maxWeight = Math.max(...data.holdings.map((h) => h.weight), 0.0001);
  data.holdings.forEach((h, i) => {
    const tr = document.createElement("tr");
    const pct = Math.min(100, (h.weight / maxWeight) * 100);
    tr.innerHTML =
      `<td class="col-rank">${i + 1}</td>` +
      `<td class="code-cell">${esc(h.code)}</td>` +
      `<td>${esc(h.name)}</td>` +
      `<td class="num">${fmtInt(h.share)}</td>` +
      `<td class="num"><span class="weight-cell">${fmtPct(h.weight)}` +
      `<span class="weight-bar"><i style="width:${pct}%"></i></span></span></td>`;
    tbody.appendChild(tr);
  });
}

// ---- Base date presets ----
function shiftDate(iso, preset) {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  if (preset === "1d") dt.setDate(dt.getDate() - 1);
  else if (preset === "1w") dt.setDate(dt.getDate() - 7);
  else if (preset === "1m") dt.setMonth(dt.getMonth() - 1);
  const p = (n) => String(n).padStart(2, "0");
  return `${dt.getFullYear()}-${p(dt.getMonth() + 1)}-${p(dt.getDate())}`;
}

// ---- View tabs ----
function setView(view) {
  state.view = view;
  document.querySelectorAll(".view-tab").forEach((t) => {
    const on = t.dataset.view === view;
    t.classList.toggle("active", on);
    t.setAttribute("aria-selected", on ? "true" : "false");
  });
  $("#portfolioSection").classList.toggle("hidden", view !== "portfolio");
  $("#diffSection").classList.toggle("hidden", view !== "diff");
}

// ---- Diff ----
function setDiffEmpty() {
  $("#diffMeta").textContent = "";
  $("#diffBlocks").innerHTML = "";
  $("#diffHint").classList.remove("hidden");
  $("#diffTabBadge").classList.add("hidden");
}

async function loadDiff() {
  const base = $("#baseInput").value;
  const cur = $("#dateInput").value;
  if (!base || !cur) {
    setDiffEmpty();
    return;
  }
  setStatus("比對中…");
  let data;
  try {
    data = await (await fetch(`/api/diff?etf=${state.etf}&date=${cur}&base=${base}`)).json();
  } catch (e) {
    setStatus("比對連線失敗", true);
    return;
  }
  if (data.error) {
    setStatus(data.error, true);
    return;
  }
  setStatus("");
  renderDiff(data);
}

function holdingsTable(rows, cols) {
  if (!rows.length) return '<p class="empty">無變動項目</p>';
  const head = cols.map((c) => `<th class="${c.num ? "num" : ""}">${c.label}</th>`).join("");
  const body = rows
    .map(
      (r) =>
        "<tr>" +
        cols.map((c) => `<td class="${c.cls || (c.num ? "num" : "")}">${c.render(r)}</td>`).join("") +
        "</tr>"
    )
    .join("");
  return `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function renderDiff(data) {
  $("#diffMeta").textContent = `${data.base} → ${data.date}`;
  $("#diffHint").classList.add("hidden");
  const blocks = $("#diffBlocks");
  blocks.innerHTML = "";

  const baseCols = [
    { label: "代號", cls: "code-cell", render: (r) => esc(r.code) },
    { label: "名稱", render: (r) => esc(r.name) },
    { label: "股數", num: true, render: (r) => fmtInt(r.share) },
    { label: "權重", num: true, render: (r) => fmtPct(r.weight) },
  ];
  const changedCols = [
    { label: "代號", cls: "code-cell", render: (r) => esc(r.code) },
    { label: "名稱", render: (r) => esc(r.name) },
    { label: "股數", num: true, render: (r) => fmtInt(r.share) },
    { label: "股數增減", num: true, render: (r) => deltaCell(r.share_delta) },
    { label: "權重", num: true, render: (r) => fmtPct(r.weight) },
    { label: "權重增減", num: true, render: (r) => deltaCell(r.weight_delta, true) },
  ];

  const groups = [
    { key: "added", title: "新增持股", badge: "add", cols: baseCols },
    { key: "removed", title: "移除持股", badge: "remove", cols: baseCols },
    { key: "changed", title: "股數 / 權重變動", badge: "change", cols: changedCols },
  ];

  groups.forEach((g) => {
    const rows = data[g.key] || [];
    const div = document.createElement("div");
    div.className = "diff-group";
    div.innerHTML =
      `<h3>${g.title}<span class="badge ${g.badge}">${rows.length}</span></h3>` +
      holdingsTable(rows, g.cols);
    blocks.appendChild(div);
  });

  const total =
    (data.added || []).length + (data.removed || []).length + (data.changed || []).length;
  const badge = $("#diffTabBadge");
  badge.textContent = total;
  badge.classList.toggle("hidden", total === 0);
}

// ---- Events ----
function loadLatest() {
  $("#baseInput").value = "";
  setDiffEmpty();
  setView("portfolio");
  loadPortfolio(null);
}

$("#queryBtn").onclick = async () => {
  const d = $("#dateInput").value;
  if (!d) return;
  await loadPortfolio(d);
  await loadDiff();
};
$("#baseInput").onchange = async () => {
  await loadDiff();
  if ($("#baseInput").value) setView("diff");
};
$("#baseClear").onclick = () => {
  $("#baseInput").value = "";
  setDiffEmpty();
  setView("portfolio");
};
document.querySelectorAll(".preset-btn").forEach((b) => {
  b.onclick = async () => {
    const cur = $("#dateInput").value;
    if (!cur) return;
    $("#baseInput").value = shiftDate(cur, b.dataset.preset);
    await loadDiff();
    setView("diff");
  };
});
document.querySelectorAll(".view-tab").forEach((t) => {
  t.onclick = () => setView(t.dataset.view);
});

// ---- Boot ----
(async function main() {
  initTheme();
  await initEtfs();
  await loadLatest();
})();
