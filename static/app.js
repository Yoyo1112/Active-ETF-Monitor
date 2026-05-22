"use strict";

const state = { etf: null, etfs: [] };

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
function fmtSigned(n, pct = false) {
  const v = pct ? Number(n).toFixed(2) + "%" : fmtInt(Math.abs(n));
  const sign = n > 0 ? "+" : n < 0 ? "−" : "";
  return sign + (pct ? "" : "") + (n < 0 && pct ? "" : "") + v.replace("-", "");
}
function deltaCell(n, pct = false) {
  const cls = n > 0 ? "up" : n < 0 ? "down" : "";
  const sign = n > 0 ? "+" : n < 0 ? "−" : "";
  const val = pct ? Math.abs(n).toFixed(2) + "%" : fmtInt(Math.abs(n));
  return `<span class="${cls}">${sign}${val}</span>`;
}

// ---- 載入 ETF 清單與分頁 ----
async function initEtfs() {
  state.etfs = await (await fetch("/api/etfs")).json();
  const tabs = $("#etfTabs");
  tabs.innerHTML = "";
  state.etfs.forEach((code, i) => {
    const b = document.createElement("button");
    b.className = "etf-tab" + (i === 0 ? " active" : "");
    b.textContent = code;
    b.onclick = () => selectEtf(code);
    tabs.appendChild(b);
  });
  state.etf = state.etfs[0];
}

function selectEtf(code) {
  state.etf = code;
  document.querySelectorAll(".etf-tab").forEach((t) => {
    t.classList.toggle("active", t.textContent === code);
  });
  loadLatest();
}

// ---- 投資組合 ----
async function loadPortfolio(dateStr) {
  setStatus("讀取中…");
  const url = "/api/portfolio?etf=" + state.etf + (dateStr ? "&date=" + dateStr : "");
  let data;
  try {
    data = await (await fetch(url)).json();
  } catch (e) {
    setStatus("連線失敗，請稍後再試", true);
    return null;
  }
  if (data.error) {
    setStatus(data.error, true);
    return null;
  }
  renderPortfolio(data);
  await refreshDates();
  setStatus(data.cached ? "（來自快取）" : "");
  return data;
}

function renderPortfolio(data) {
  const tbody = $("#portfolioTable tbody");
  tbody.innerHTML = "";
  $("#portfolioMeta").textContent =
    data.tran_date ? `｜${data.tran_date}　共 ${data.holdings.length} 檔` : "";

  if (!data.holdings || !data.holdings.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="empty">${
      data.message || "查無資料"
    }</td></tr>`;
    return;
  }
  if (data.tran_date) $("#dateInput").value = data.tran_date;

  data.holdings.forEach((h, i) => {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${i + 1}</td><td>${h.code}</td><td>${h.name}</td>` +
      `<td class="num">${fmtInt(h.share)}</td>` +
      `<td class="num">${fmtPct(h.weight)}</td>`;
    tbody.appendChild(tr);
  });
}

// ---- 比較基準日下拉 ----
async function refreshDates() {
  const dates = await (await fetch("/api/dates?etf=" + state.etf)).json();
  const sel = $("#baseSelect");
  const cur = $("#dateInput").value;
  const prev = sel.value;
  sel.innerHTML = '<option value="">（不比較）</option>';
  dates.forEach((d) => {
    if (d === cur) return; // 不跟自己比
    const o = document.createElement("option");
    o.value = d;
    o.textContent = d;
    sel.appendChild(o);
  });
  if (prev && [...sel.options].some((o) => o.value === prev)) sel.value = prev;
}

// ---- 差異比對 ----
async function loadDiff() {
  const base = $("#baseSelect").value;
  const cur = $("#dateInput").value;
  const sec = $("#diffSection");
  if (!base || !cur) {
    sec.classList.add("hidden");
    return;
  }
  setStatus("比對中…");
  let data;
  try {
    data = await (
      await fetch(`/api/diff?etf=${state.etf}&date=${cur}&base=${base}`)
    ).json();
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
  if (!rows.length) return '<p class="empty">無</p>';
  const head = cols.map((c) => `<th class="${c.num ? "num" : ""}">${c.label}</th>`).join("");
  const body = rows
    .map(
      (r) =>
        "<tr>" +
        cols.map((c) => `<td class="${c.num ? "num" : ""}">${c.render(r)}</td>`).join("") +
        "</tr>"
    )
    .join("");
  return `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function renderDiff(data) {
  $("#diffMeta").textContent = `｜${data.base} → ${data.date}`;
  const blocks = $("#diffBlocks");
  blocks.innerHTML = "";

  const baseCols = [
    { label: "代號", render: (r) => r.code },
    { label: "名稱", render: (r) => r.name },
    { label: "股數", num: true, render: (r) => fmtInt(r.share) },
    { label: "權重", num: true, render: (r) => fmtPct(r.weight) },
  ];
  const changedCols = [
    { label: "代號", render: (r) => r.code },
    { label: "名稱", render: (r) => r.name },
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

  $("#diffSection").classList.remove("hidden");
}

// ---- 事件 ----
function loadLatest() {
  $("#baseSelect").value = "";
  $("#diffSection").classList.add("hidden");
  loadPortfolio(null);
}

$("#queryBtn").onclick = async () => {
  const d = $("#dateInput").value;
  if (!d) return;
  await loadPortfolio(d);
  await loadDiff();
};
$("#baseSelect").onchange = loadDiff;

// ---- 啟動 ----
(async function main() {
  await initEtfs();
  await loadLatest();
})();
