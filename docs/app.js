"use strict";

const DATA_URL = "./data/dashboard.json";

const state = {
  payload: null,
  latestRows: [],
  filters: { query: "", market: "all", type: "all" },
  sort: { key: "market", direction: "asc" },
  latestExpanded: false,
  memoryExpanded: false,
  monthlyExpanded: false,
};

const labels = {
  market: "市場",
  rank: "名次",
  code: "代碼",
  name: "名稱",
  security_type: "類型",
  close: "收盤價",
  change_percent: "漲跌幅",
  net_buy_lots: "買超張數",
  volume_lots: "成交量",
  buy_volume_percent: "買超比",
  stars: "星等",
  capital_percent: "股本占比",
};

const typeText = {
  ordinary_stock: "普通股",
  etf: "ETF",
  bond_etf: "債券ETF",
  leveraged_etf: "槓桿ETF",
  inverse_etf: "反向ETF",
  active_etf: "主動式ETF",
  etn: "ETN",
  dr: "DR",
  fund: "基金型",
  other: "其他",
};

const flowStateText = {
  buy_top15: "最新交易日入榜",
  unranked_unknown: "最新交易日未入榜（方向未知）",
};

const numberFormat = new Intl.NumberFormat("zh-TW", { maximumFractionDigits: 2 });
const integerFormat = new Intl.NumberFormat("zh-TW", { maximumFractionDigits: 0 });
const dateFormat = new Intl.DateTimeFormat("zh-TW", {
  timeZone: "Asia/Taipei",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});
const dateTimeFormat = new Intl.DateTimeFormat("zh-TW", {
  timeZone: "Asia/Taipei",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

document.addEventListener("DOMContentLoaded", init);

async function init() {
  bindControls();
  try {
    const response = await fetch(DATA_URL, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    validatePayload(payload);
    state.payload = payload;
    renderDashboard(payload);
    announce(`已載入 ${displayDate(payload.data_date)} 的主力籌碼資料。`);
  } catch (error) {
    console.error("Dashboard load failed:", error);
    renderFatalState();
  }
}

function validatePayload(payload) {
  const required = ["generated_at", "data_date", "status", "market_summary", "latest", "rolling_20d", "monthly", "report_links", "quality"];
  const missing = required.filter((key) => !(key in payload));
  if (missing.length) throw new Error(`缺少必要欄位：${missing.join(", ")}`);
  if (!payload.latest || !Array.isArray(payload.latest.listed) || !Array.isArray(payload.latest.otc)) {
    throw new Error("latest.listed 與 latest.otc 必須是陣列");
  }
}

function bindControls() {
  document.querySelector("#rank-search").addEventListener("input", (event) => {
    state.filters.query = event.target.value.trim().toLocaleLowerCase("zh-Hant");
    renderLatest();
  });

  document.querySelector("#market-filter").addEventListener("change", (event) => {
    if (event.target.name === "market") {
      state.filters.market = event.target.value;
      renderLatest();
    }
  });

  document.querySelector("#type-filter").addEventListener("change", (event) => {
    state.filters.type = event.target.value;
    renderLatest();
  });

  document.querySelectorAll("#latest-table th[data-key] button").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.closest("th").dataset.key;
      if (state.sort.key === key) {
        state.sort.direction = state.sort.direction === "asc" ? "desc" : "asc";
      } else {
        state.sort = { key, direction: "asc" };
      }
      renderLatest();
    });
  });

  document.querySelector("#memory-toggle").addEventListener("click", () => {
    state.memoryExpanded = !state.memoryExpanded;
    renderMemory(normalizeRows(state.payload?.rolling_20d));
  });

  document.querySelector("#latest-toggle").addEventListener("click", () => {
    state.latestExpanded = !state.latestExpanded;
    renderLatest();
  });

  document.querySelector("#monthly-toggle").addEventListener("click", () => {
    state.monthlyExpanded = !state.monthlyExpanded;
    renderMonthly(state.payload?.monthly);
  });
}

function renderDashboard(payload) {
  document.querySelector("#demo-banner").hidden = !payload.sample_data;
  document.querySelector("#data-date").textContent = payload.data_date ? displayDate(payload.data_date) : "尚未確認";
  document.querySelector("#generated-at").textContent = displayDateTime(payload.generated_at);

  const qaPassed = payload.quality?.latest_qa_result?.passed === true;
  document.querySelector("#qa-status").textContent = qaPassed ? "QA 通過" : "QA 未通過";

  state.latestRows = [
    ...payload.latest.listed.map((row) => ({ ...row, market_group: "listed" })),
    ...payload.latest.otc.map((row) => ({ ...row, market_group: "otc" })),
  ];

  renderQuality(payload);
  renderLatest();
  renderMemory(normalizeRows(payload.rolling_20d));
  renderMonthly(payload.monthly);
  renderReportLinks(payload.report_links);
}

function renderQuality(payload) {
  const quality = payload.quality || {};
  const listedCount = numberOr(quality.listed_rows, payload.latest.listed.length);
  const otcCount = numberOr(quality.otc_rows, payload.latest.otc.length);
  const formulaErrors = numberOr(quality.formula_errors, 0);
  const coverage = Array.isArray(quality.date_coverage)
    ? `${quality.date_coverage.length} 個交易日`
    : value(quality.date_coverage, "—");
  const qaPassed = quality.latest_qa_result?.passed === true;

  const metrics = [
    { label: "上市排行", value: `${listedCount} / 15`, tone: listedCount === 15 ? "good" : "bad" },
    { label: "上櫃排行", value: `${otcCount} / 15`, tone: otcCount === 15 ? "good" : "bad" },
    { label: "公式錯誤", value: `${formulaErrors} 筆`, tone: formulaErrors === 0 ? "good" : "bad" },
    { label: "交易日覆蓋", value: coverage, tone: Array.isArray(quality.date_coverage) && quality.date_coverage.length >= 20 ? "good" : "warn" },
  ];

  const host = document.querySelector("#quality-metrics");
  host.replaceChildren(...metrics.map((metric) => createMetric(metric)));
  document.querySelector("#quality-summary").textContent = qaPassed
    ? "獨立驗證通過，頁面可發布。"
    : "最新驗證未通過。請查看來源狀態與缺漏。";

}

function renderLatest() {
  const body = document.querySelector("#latest-table tbody");
  const empty = document.querySelector("#latest-state");
  const query = state.filters.query;

  const rows = state.latestRows.filter((row) => {
    const matchesQuery = !query || `${row.code} ${row.name}`.toLocaleLowerCase("zh-Hant").includes(query);
    const matchesMarket = state.filters.market === "all" || row.market_group === state.filters.market;
    const matchesType = matchesSecurityType(row.security_type, state.filters.type);
    return matchesQuery && matchesMarket && matchesType;
  }).sort(compareRows);

  const compactMobile = window.matchMedia("(max-width: 700px)").matches
    && !state.latestExpanded
    && !state.filters.query
    && state.filters.market === "all"
    && state.filters.type === "all";
  const visibleRows = compactMobile ? rows.filter((row) => Number(row.rank) <= 5) : rows;
  updateSortHeaders();
  body.replaceChildren(...visibleRows.map(createLatestRow));
  document.querySelector("#rank-result-count").textContent = compactMobile
    ? `先顯示上市前5＋上櫃前5，共 ${rows.length} 筆可展開`
    : `顯示 ${rows.length} 筆，共 ${state.latestRows.length} 筆已載入排行`;
  const latestToggle = document.querySelector("#latest-toggle");
  const canCompact = window.matchMedia("(max-width: 700px)").matches
    && !state.filters.query && state.filters.market === "all" && state.filters.type === "all";
  latestToggle.hidden = !canCompact;
  latestToggle.setAttribute("aria-expanded", String(state.latestExpanded));
  latestToggle.textContent = state.latestExpanded ? "收合為各市場前5" : "展開完整30筆";
  empty.hidden = visibleRows.length > 0;
  if (!visibleRows.length) setStatePanel(empty, "沒有符合條件的股票", "請清除搜尋字詞，或改選其他市場與證券類型。");
}

function createLatestRow(row) {
  const tr = document.createElement("tr");
  const market = row.market_group === "listed" ? "上市" : "上櫃";
  tr.dataset.market = `${market}前15名`;
  if (Number(row.rank) === 1) tr.classList.add("market-start");
  if (Number(row.rank) <= 3) tr.classList.add("top-rank");
  const values = [
    badgeValue(market, "market-tag"),
    textValue(row.rank),
    textValue(row.code, "code-cell"),
    textValue(row.name, "name-cell"),
    textValue(typeText[row.security_type] || row.security_type || "不可用"),
    numberValue(row.close, 2),
    percentValue(row.change_percent, 2, true),
    numberValue(row.net_buy_lots, 0),
    numberValue(row.volume_lots, 0),
    percentValue(row.buy_volume_percent, 2),
    textValue(starValue(row.stars), "star-cell"),
    percentValue(row.capital_percent, 4),
  ];

  values.forEach((cell, index) => {
    cell.dataset.label = Object.values(labels)[index];
    if ([5, 6, 7, 8, 9, 11].includes(index)) cell.classList.add("numeric");
    tr.append(cell);
  });
  return tr;
}

function renderMemory(rows) {
  const collapsedLimit = compactRowLimit();
  const visibleRows = rows.slice(0, state.memoryExpanded ? 20 : collapsedLimit);
  const body = document.querySelector("#memory-table tbody");
  const empty = document.querySelector("#memory-state");
  body.replaceChildren(...visibleRows.map((row) => {
    const tr = document.createElement("tr");
    const cells = [
      textValue(`${value(row.code, "—")} ${value(row.name, "")}`, "name-cell"),
      numberValue(pick(row, "appearance_count", "top15_days", "appearances", "buy_top15_days"), 0),
      textValue(streakText(pick(row, "longest_streak", "streak"))),
      signedNumberValue(pick(row, "observed_net_buy_lots", "net_buy_lots", "observed_buy_lots")),
      percentValue(pick(row, "weighted_buy_percent", "weighted_buy_ratio", "buy_volume_percent"), 2),
      textValue(flowStateText[row.buy_sell_state] || value(pick(row, "latest_state", "status"), "不可用")),
    ];
    ["代碼／名稱", "前15日數", "最長連續", "觀察淨買超", "加權買超比", "最新狀態"].forEach((label, index) => {
      cells[index].dataset.label = label;
      if ([1, 2, 3, 4].includes(index)) cells[index].classList.add("numeric");
      tr.append(cells[index]);
    });
    return tr;
  }));
  empty.hidden = visibleRows.length > 0;
  updateTableToggle("memory-toggle", state.memoryExpanded, rows.length, collapsedLimit, "完整20檔");
  if (!rows.length) setStatePanel(empty, "尚無20交易日記憶", "累積足夠的每日觀測後，這裡會顯示連續入榜與買賣方向。");
}

function renderMonthly(monthly) {
  const metadata = monthly?.metadata || monthly || {};
  const rows = normalizeRows(monthly?.rows || monthly?.summary_rows || monthly?.summary);
  const ordinaryRows = rows.filter((row) => row.security_type === "ordinary_stock");
  const fundRows = rows.filter((row) => row.security_type !== "ordinary_stock");
  const collapsedLimit = compactRowLimit();
  const visibleRows = ordinaryRows.slice(0, state.monthlyExpanded ? 20 : collapsedLimit);
  document.querySelector("#monthly-period").textContent = value(metadata.period || metadata.month, "尚無月份");

  const facts = [
    ["已觀察交易日", suffix(metadata.trading_days_observed ?? metadata.trading_days, " 日")],
    ["普通股入榜", suffix(ordinaryRows.length, " 檔")],
    ["ETF／其他資金流", suffix(fundRows.length, " 檔")],
  ];
  const factHost = document.querySelector("#monthly-facts");
  factHost.replaceChildren(...facts.map(([term, description]) => {
    const wrapper = document.createElement("div");
    const dt = el("dt"); dt.textContent = term;
    const dd = el("dd"); dd.textContent = description;
    wrapper.append(dt, dd);
    return wrapper;
  }));
  const limitation = value(metadata.note || metadata.limitations, "月報只彙整具證據的排行觀測，不把未入榜視為零。");
  document.querySelector("#monthly-note").textContent = `${limitation} 目前顯示 ${visibleRows.length} 檔普通股；ETF／其他請見完整月報。`;

  const body = document.querySelector("#monthly-table tbody");
  const empty = document.querySelector("#monthly-state");
  body.replaceChildren(...visibleRows.map((row) => {
    const tr = document.createElement("tr");
    const cells = [
      textValue(`${value(row.code, "—")} ${value(row.name, "")}`, "name-cell"),
      textValue(marketText(row.market)),
      numberValue(pick(row, "buy_top15_days", "top15_days", "appearance_days", "appearances"), 0),
      textValue(streakText(pick(row, "longest_streak", "streak"))),
      percentValue(pick(row, "weighted_buy_percent", "weighted_buy_ratio"), 2),
      percentValue(pick(row, "monthly_capital_percent", "capital_percent"), 4),
      textValue(value(pick(row, "classification", "category"), "不可用")),
    ];
    ["代碼／名稱", "市場", "入榜日數", "最長連續", "加權買超比", "月買超占股本", "分類"].forEach((label, index) => {
      cells[index].dataset.label = label;
      if ([2, 3, 4, 5].includes(index)) cells[index].classList.add("numeric");
      tr.append(cells[index]);
    });
    return tr;
  }));
  empty.hidden = visibleRows.length > 0;
  updateTableToggle("monthly-toggle", state.monthlyExpanded, ordinaryRows.length, collapsedLimit, "完整月度清單");
  if (!visibleRows.length) setStatePanel(empty, "尚無普通股月報", "每月第一天完成上月整理後，普通股候選會顯示在這裡。");
}

function renderReportLinks(links) {
  const names = { daily: "每日完整報告", weekly: "每週連續入榜", analysis: "週日策略分析", monthly: "月度籌碼整理" };
  const host = document.querySelector("#report-links");
  const items = Object.entries(links || {}).filter(([, href]) => typeof href === "string" && href.trim());
  if (!items.length) {
    const text = el("p");
    text.textContent = "尚未發布可讀取的報告連結。";
    host.replaceChildren(text);
    return;
  }
  host.replaceChildren(...items.map(([key, href]) => {
    const link = el("a", "report-link");
    link.href = safeLink(href);
    link.textContent = names[key] || key;
    return link;
  }));
}

function renderFatalState() {
  document.querySelector("#data-date").textContent = "無法載入";
  document.querySelector("#qa-status").textContent = "QA 未執行";
  document.querySelector("#quality-summary").textContent = "資料檔無法讀取，未顯示任何舊數據。";
  document.querySelector("#quality-metrics").replaceChildren();
  setStatePanel(document.querySelector("#latest-state"), "資料載入失敗", "請稍後重新整理；維護者可檢查 docs/data/dashboard.json 與GitHub Actions執行紀錄。");
  document.querySelector("#latest-state").hidden = false;
  document.querySelector("#latest-table").hidden = true;
  setStatePanel(document.querySelector("#memory-state"), "記憶資料不可用", "主資料載入失敗，因此沒有顯示可能過期的歷史結果。");
  document.querySelector("#memory-state").hidden = false;
  document.querySelector("#memory-table").hidden = true;
  setStatePanel(document.querySelector("#monthly-state"), "月報不可用", "主資料載入失敗，請查看品質狀態後再試。");
  document.querySelector("#monthly-state").hidden = false;
  document.querySelector("#monthly-table").hidden = true;
  announce("主力籌碼資料載入失敗。頁面沒有顯示舊資料。 ");
}

function createMetric(metric) {
  const card = el("div", "metric");
  const label = el("p", "metric__label"); label.textContent = metric.label;
  const amount = el("p", `metric__value ${metric.tone}`); amount.textContent = metric.value;
  card.append(label, amount);
  return card;
}

function compactRowLimit() {
  return window.matchMedia("(max-width: 700px)").matches ? 6 : 10;
}

function updateTableToggle(id, expanded, total, collapsedLimit, label) {
  const button = document.querySelector(`#${id}`);
  const canExpand = total > collapsedLimit;
  button.hidden = !canExpand;
  button.setAttribute("aria-expanded", String(expanded));
  button.textContent = expanded ? "收合重點清單" : `展開${label}（${Math.min(20, total)}檔）`;
}

function compareRows(a, b) {
  const key = state.sort.key;
  let left = key === "market" ? a.market_group : a[key];
  let right = key === "market" ? b.market_group : b[key];
  if (key === "stars") {
    left = starCount(left);
    right = starCount(right);
  }
  const leftNum = numeric(left);
  const rightNum = numeric(right);
  let result;
  if (leftNum !== null && rightNum !== null) result = leftNum - rightNum;
  else result = String(left ?? "").localeCompare(String(right ?? ""), "zh-Hant", { numeric: true });
  if (result === 0 && key !== "rank") result = numberOr(a.rank, 999) - numberOr(b.rank, 999);
  return state.sort.direction === "asc" ? result : -result;
}

function updateSortHeaders() {
  document.querySelectorAll("#latest-table th[data-key]").forEach((th) => {
    const active = th.dataset.key === state.sort.key;
    if (active) th.setAttribute("aria-sort", state.sort.direction === "asc" ? "ascending" : "descending");
    else th.removeAttribute("aria-sort");
  });
}

function matchesSecurityType(type, filter) {
  if (filter === "all") return true;
  if (filter === "ordinary_stock") return type === "ordinary_stock";
  const funds = new Set(["etf", "bond_etf", "leveraged_etf", "inverse_etf", "active_etf", "fund"]);
  if (filter === "fund") return funds.has(type);
  return type !== "ordinary_stock" && !funds.has(type);
}

function marketText(market) {
  const normalized = String(market || "").toLowerCase();
  if (["listed", "twse", "上市"].includes(normalized)) return "上市";
  if (["otc", "tpex", "上櫃"].includes(normalized)) return "上櫃";
  return value(market, "不可用");
}

function displayDate(input) {
  if (!input) return "不可用";
  const date = parseDate(input);
  return date ? dateFormat.format(date) : String(input);
}

function displayDateTime(input) {
  if (!input) return "不可用";
  const date = new Date(input);
  return Number.isNaN(date.getTime()) ? String(input) : dateTimeFormat.format(date);
}

function parseDate(input) {
  const match = String(input).match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) {
    const parsed = new Date(input);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }
  return new Date(`${match[1]}-${match[2]}-${match[3]}T12:00:00+08:00`);
}

function numberValue(input, digits) {
  const td = el("td");
  const num = numeric(input);
  td.textContent = num === null ? "不可用" : new Intl.NumberFormat("zh-TW", { minimumFractionDigits: 0, maximumFractionDigits: digits }).format(num);
  return td;
}

function signedNumberValue(input) {
  const td = numberValue(input, 0);
  const num = numeric(input);
  if (num !== null && num > 0) { td.textContent = `+${integerFormat.format(num)}`; td.classList.add("change-up"); }
  if (num !== null && num < 0) td.classList.add("change-down");
  return td;
}

function percentValue(input, digits, signed = false) {
  const td = el("td");
  const num = numeric(input);
  if (num === null) { td.textContent = "不可用"; return td; }
  const formatted = new Intl.NumberFormat("zh-TW", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(num);
  td.textContent = `${signed && num > 0 ? "+" : ""}${formatted}%`;
  if (signed && num > 0) td.classList.add("change-up");
  if (signed && num < 0) td.classList.add("change-down");
  return td;
}

function textValue(input, className = "") {
  const td = el("td", className);
  td.textContent = value(input, "不可用");
  return td;
}

function badgeValue(input, className) {
  const td = el("td");
  const span = el("span", className);
  span.textContent = value(input, "不可用");
  td.append(span);
  return td;
}

function starValue(input) {
  const count = starCount(input);
  return count ? "★".repeat(Math.min(count, 5)) : "不可用";
}

function starCount(input) {
  if (typeof input === "number") return input;
  if (typeof input === "string") {
    const stars = (input.match(/★/g) || []).length;
    return stars || numeric(input) || 0;
  }
  return 0;
}

function streakText(input) {
  const num = numeric(input);
  return num === null ? "不可用" : `${numberFormat.format(num)} 日`;
}

function suffix(input, unit) {
  return input === null || input === undefined || input === "" ? "不可用" : `${input}${unit}`;
}

function normalizeRows(input) {
  if (Array.isArray(input)) return input;
  if (input && Array.isArray(input.rows)) return input.rows;
  if (input && Array.isArray(input.observations)) return input.observations;
  return [];
}

function pick(object, ...keys) {
  for (const key of keys) {
    if (object?.[key] !== null && object?.[key] !== undefined && object?.[key] !== "") return object[key];
  }
  return null;
}

function value(input, fallback) {
  return input === null || input === undefined || input === "" ? fallback : String(input);
}

function numeric(input) {
  if (typeof input === "number" && Number.isFinite(input)) return input;
  if (typeof input !== "string") return null;
  const cleaned = input.replace(/[%+,\s]/g, "");
  if (!cleaned || !Number.isFinite(Number(cleaned))) return null;
  return Number(cleaned);
}

function numberOr(input, fallback) {
  return numeric(input) ?? fallback;
}

function setStatePanel(panel, title, detail) {
  const strong = el("strong"); strong.textContent = title;
  const text = document.createTextNode(detail);
  panel.replaceChildren(strong, text);
}

function safeLink(href) {
  const raw = String(href).trim();
  if (!raw || /^(javascript|data|vbscript):/i.test(raw)) return "#";
  if (/^[a-z][a-z\d+.-]*:/i.test(raw) && !/^https?:/i.test(raw)) return "#";
  return raw;
}

function el(tagName, className = "") {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  return element;
}

function announce(message) {
  document.querySelector("#app-announcer").textContent = message;
}
