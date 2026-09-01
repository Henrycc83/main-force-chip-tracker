import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const root = new URL("../", import.meta.url);
const [html, css, js, rawJson] = await Promise.all([
  readFile(new URL("docs/index.html", root), "utf8"),
  readFile(new URL("docs/styles.css", root), "utf8"),
  readFile(new URL("docs/app.js", root), "utf8"),
  readFile(new URL("docs/data/dashboard.json", root), "utf8"),
]);

const data = JSON.parse(rawJson);
const requiredTopLevel = [
  "generated_at", "data_date", "status", "market_summary", "latest",
  "rolling_20d", "monthly", "report_links", "quality",
];
for (const key of requiredTopLevel) assert.ok(key in data, `missing top-level key: ${key}`);

assert.match(data.generated_at, /[+-]\d{2}:\d{2}$/, "generated_at must carry an explicit UTC offset");
assert.ok(["confirmed", "partial", "no_new_data", "unavailable"].includes(data.status));
assert.equal(data.latest.listed.length, 15, "sample listed ranking must contain 15 rows");
assert.equal(data.latest.otc.length, 15, "sample OTC ranking must contain 15 rows");
assert.ok(data.rolling_20d.every((row) => "appearance_count" in row && "buy_sell_state" in row), "rolling memory schema mismatch");
assert.ok(data.monthly.summary_rows.every((row) => [
  "buy_top15_days", "longest_streak", "observed_buy_lots", "weighted_buy_percent",
  "month_price_change_percent", "monthly_capital_percent", "classification", "evidence_status",
].every((key) => key in row)), "monthly summary schema mismatch");

const requiredRowKeys = [
  "market", "rank", "code", "name", "security_type", "close", "change_percent",
  "net_buy_lots", "volume_lots", "buy_volume_percent", "stars", "capital_percent",
  "evidence_status", "source_date", "denominator_date",
];

for (const [market, rows] of Object.entries(data.latest)) {
  assert.deepEqual(rows.map((row) => row.rank), Array.from({ length: 15 }, (_, i) => i + 1), `${market} ranks must be 1..15`);
  assert.equal(new Set(rows.map((row) => row.code)).size, 15, `${market} codes must be unique`);
  for (const row of rows) {
    for (const key of requiredRowKeys) assert.ok(key in row, `${market}/${row.code} missing ${key}`);
    const ratio = Number(row.buy_volume_percent);
    const expectedStars = ratio <= 5 ? 1 : ratio <= 10 ? 2 : ratio <= 15 ? 3 : ratio <= 20 ? 4 : 5;
    assert.equal(row.stars, expectedStars, `${market}/${row.code} star boundary mismatch`);
  }
}

for (const id of [
  "main-content", "data-date", "generated-at", "quality-metrics", "rank-search",
  "market-filter", "type-filter", "latest-table", "memory-table", "monthly-table",
  "latest-state", "memory-state", "monthly-state", "app-announcer",
]) {
  assert.ok(html.includes(`id="${id}"`), `missing required UI hook #${id}`);
}

assert.ok(html.includes("class=\"skip-link\""), "skip link is required");
assert.ok(html.includes("aria-live"), "live-region feedback is required");
assert.ok(html.includes("app.js?v="), "production script must be cache-busted after UI releases");
assert.ok(css.includes("prefers-reduced-motion"), "reduced-motion support is required");
assert.ok(css.includes("focus-visible"), "visible keyboard focus is required");
assert.ok(css.includes("@media (max-width: 700px)"), "mobile layout is required");
assert.ok(!js.includes("row-evidence"), "ranking rows must not show evidence labels");
assert.ok(!js.includes("· 分母"), "denominator dates must not be shown in ranking badges");
assert.ok(!html.includes('id="overall-status"'), "overall evidence status must remain hidden");
assert.ok(!html.includes('id="source-health"'), "source evidence badges must remain hidden");
assert.ok(!js.includes("innerHTML"), "dashboard rendering must avoid innerHTML injection");

const headerStart = html.indexOf('<table id="latest-table">');
const headerEnd = html.indexOf("</thead>", headerStart);
const latestHeader = html.slice(headerStart, headerEnd);
assert.ok(latestHeader.lastIndexOf('data-key="capital_percent"') > latestHeader.lastIndexOf('data-key="stars"'), "capital_percent must remain the final latest-table field");

console.log("Static dashboard checks passed: schema, 15+15 ranks, star boundaries, accessibility and responsive hooks.");
