# 股票盈虧追蹤（含股息）

簡易本地網頁應用，輸入買入日期、代號、買入價與股數後，以今日價格與現金股息計算未實現盈虧。

## 環境需求

- Python 3.10+
- 建議使用虛擬環境

## 安裝與啟動

```bash
cd /workspace/stock-pnl-app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

瀏覽器開啟終端機顯示的本機網址（通常為 `http://localhost:8501`）。

若虛擬環境已建好，之後只需：

```bash
cd /workspace/stock-pnl-app
source .venv/bin/activate
streamlit run app.py
```

## 煙霧測試（不開 UI）

```bash
cd /workspace/stock-pnl-app
source .venv/bin/activate
python smoke_test.py
```

會查詢 AAPL 與 0700.HK 的現價與樣本期股息總額。

## 代號輸入

| 市場 | 輸入範例 | 實際查詢 |
|------|----------|----------|
| 美股 | `AAPL`、`MSFT` | 原樣 |
| 港股 | `0700`、`700`、`0700.HK` | `0700.HK` |

## 限制與注意

- **無自動換匯**：USD / HKD 持倉分開顯示與加總。
- 價格可能有延遲；股息以 yfinance 除淨日為準，僅計現金股息。
- 若你輸入的是拆股前買入價，盈虧可能不準——請用拆股後等效買入價。
- 資料來源為 Yahoo Finance，偶發無資料或代號無效時會顯示錯誤提示。
