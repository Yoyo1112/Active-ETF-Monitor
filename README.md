# 主動式 ETF 投資組合查詢與差異比對 (00981A / 00403A)

從 [ezmoney PCF 申購買回清單](https://www.ezmoney.com.tw/ETF/Transaction/PCF) 抓取
**00981A**、**00403A** 兩檔主動式 ETF 的每日投資組合，可：

- 選某一天，看當天投資組合（股票代號、名稱、持有股數、持有權重）
- 與之前任一天比對差異（新增持股 / 移除持股 / 股數・權重變動）
- 打開網頁即自動抓最新一日

## 本機執行

```bash
pip install -r requirements.txt
python app.py
```

開瀏覽器到 <http://localhost:5000>。

驗證與雲端一致的啟動方式：

```bash
gunicorn app:app          # 預設 8000 埠
```

## 說明

- 資料即時向 ezmoney 抓取，並以 SQLite (`data/portfolio.db`) 做快取加速。
  快取清空（重部署 / 休眠）不影響正確性，因為官網有完整歷史可重抓。
- ETF 代號對應 ezmoney 內部 fundCode：00981A→49YTW、00403A→63YTW
  （見 `ezmoney.py` 的 `FUND_CODES`）。
- 基金成立日之前或非揭露日會顯示「當日無資料」。

## 檔案

| 檔案 | 用途 |
|------|------|
| `app.py` | Flask 路由與 API |
| `ezmoney.py` | 抓取 / 解析 GetPCF、民國日期轉換 |
| `store.py` | SQLite 快取 |
| `static/` | 前端單頁 (HTML/CSS/JS) |
| `render.yaml`, `Procfile` | Render 部署設定 |
