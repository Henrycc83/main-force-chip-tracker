# Main Force Chip Tracker Contract

## Output contract

The pipeline writes a static dashboard payload to `docs/data/dashboard.json`.

Required top-level keys:

- `generated_at`: ISO-8601 timestamp with Asia/Taipei offset.
- `data_date`: latest confirmed trading date or null.
- `status`: `confirmed`, `partial`, `no_new_data`, or `unavailable`.
- `market_summary`: counts and validation status for TWSE and TPEx.
- `latest`: arrays `listed` and `otc`, each containing exactly 15 rows when confirmed.
- `rolling_20d`: ordinary-stock observations with appearance, streak, buy/sell, ratio, and evidence fields.
- `monthly`: metadata and summary rows for the latest completed calendar month.
- `report_links`: relative links to daily, weekly, analysis, and monthly reports.
- `quality`: row counts, formula errors, date coverage, source health, and latest QA result.

Each latest row contains `market`, `rank`, `code`, `name`, `security_type`, `close`,
`change_percent`, `net_buy_lots`, `volume_lots`, `buy_volume_percent`, `stars`,
`capital_percent`, `evidence_status`, and source/denominator dates.

## Safety contract

- Never substitute an earlier trading date for current data.
- Never treat an unranked security as zero net buying.
- Never update a `latest` artifact unless independent validation passes.
- ETF-family securities remain separate from ordinary-stock lock-up analysis.
- All financial arithmetic uses `Decimal` and the configured boundary rules.
- AI text, when enabled, may summarize verified data but cannot create or modify numbers.
