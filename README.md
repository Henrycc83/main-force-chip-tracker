# 台股主力籌碼追蹤

可稽核的台灣上市／上櫃主力買超追蹤程式。每日台北時間 18:00 由 GitHub Actions 執行，只有在上市與上櫃同日各 15 筆、公式與日期驗證全部通過時，才更新 GitHub Pages 儀表板。

## 核心原則

- 富邦 eBroker 保留原始前 15 名；上市與上櫃分開呈現。
- 漲跌幅與成交量交叉核對 TWSE／TPEx，同日不完整就拒絕發布。
- 星級邊界固定為 5%、10%、15%、20%，邊界值歸較低級。
- 股本占比使用官方發行股數／受益單位，缺漏顯示不可用。
- ETF、ETN、DR、槓桿反向商品保留但分流，不解讀成公司鎖籌碼。
- 保存每日觀察與近 20 個交易日記憶；未入榜不視為買超 0 張。
- 週六整理連續至少 2 個交易日入榜者；週日產生含反證、驗證指標及條件式風控的候選分析。
- 每月 1 日整理上個月籌碼月報；ETF 等商品只列資金流附錄。

## 本機驗證

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m pytest -q
npm run test:frontend
```

手動更新：

```powershell
.\.venv\Scripts\python.exe -m chip_tracker.cli --root . run --dashboard-path docs\data\dashboard.json
```

輸出位於 `docs/`、`data/` 與 `reports/main-force-chips/`。網站只供研究追蹤，不構成投資建議。
