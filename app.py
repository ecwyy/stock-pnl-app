"""股票盈虧追蹤（含股息）— Streamlit 應用"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd
import streamlit as st

from pnl_core import (
    color_pnl,
    fetch_lot_data,
    fmt_money,
    fmt_pct,
    normalize_ticker,
)

st.set_page_config(
    page_title="股票盈虧追蹤（含股息）",
    page_icon="📈",
    layout="wide",
)

st.title("📈 股票盈虧追蹤（含股息）")
st.caption("財富自由 Bot · 以今日最新價格與派息計算未實現盈虧")

with st.expander("使用說明", expanded=True):
    st.markdown(
        """
**如何輸入股票代號**
- **美股**：直接輸入，例如 `AAPL`、`MSFT`、`VOO`
- **港股**：可輸入 `0700`、`700`、`0700.HK`、`9988.HK`（會自動轉成 `XXXX.HK`）

**計算邏輯**
- 成本 = 買入價 × 數量
- 市值 = 最新價 × 數量
- 價格盈虧 = 市值 − 成本
- 股息總額 = 買入日（含）至今日的現金股息（每股）× 數量
- 總盈虧 = 價格盈虧 + 股息總額

**注意**
- 美股以 **USD**、港股以 **HKD** 顯示，**不會自動換匯**；同貨幣才會加總。
- 價格可能有延遲；股息以 yfinance 除淨日為準，僅計現金股息。
- 未處理拆股調整對「你輸入的買入價」之影響——請自行使用拆股後等效買入價。
        """
    )

if "lots" not in st.session_state:
    st.session_state.lots = [
        {
            "buy_date": date(2024, 1, 2),
            "ticker": "AAPL",
            "buy_price": 185.0,
            "quantity": 10.0,
        }
    ]

st.subheader("持倉輸入")

col_btn1, col_btn2, _ = st.columns([1, 1, 4])
with col_btn1:
    if st.button("➕ 新增一筆", use_container_width=True):
        st.session_state.lots.append(
            {
                "buy_date": date.today(),
                "ticker": "",
                "buy_price": 0.0,
                "quantity": 0.0,
            }
        )
        st.rerun()
with col_btn2:
    if st.button("🗑️ 清空重設", use_container_width=True):
        st.session_state.lots = [
            {
                "buy_date": date.today(),
                "ticker": "",
                "buy_price": 0.0,
                "quantity": 0.0,
            }
        ]
        st.rerun()

lots_to_remove: list[int] = []
for i, lot in enumerate(st.session_state.lots):
    st.markdown(f"**第 {i + 1} 筆**")
    c1, c2, c3, c4, c5 = st.columns([1.4, 1.2, 1.2, 1.2, 0.5])
    with c1:
        lot["buy_date"] = st.date_input(
            "購入日期",
            value=lot["buy_date"],
            max_value=date.today(),
            key=f"buy_date_{i}",
        )
    with c2:
        lot["ticker"] = st.text_input(
            "股票代號",
            value=lot["ticker"],
            placeholder="AAPL 或 0700",
            key=f"ticker_{i}",
        )
    with c3:
        lot["buy_price"] = st.number_input(
            "買入價",
            min_value=0.0,
            value=float(lot["buy_price"] or 0),
            step=0.01,
            format="%.4f",
            key=f"buy_price_{i}",
        )
    with c4:
        lot["quantity"] = st.number_input(
            "買入數量（股）",
            min_value=0.0,
            value=float(lot["quantity"] or 0),
            step=1.0,
            format="%.4f",
            key=f"qty_{i}",
        )
    with c5:
        st.write("")
        st.write("")
        if st.button("刪除", key=f"del_{i}", use_container_width=True):
            lots_to_remove.append(i)

if lots_to_remove:
    for idx in sorted(lots_to_remove, reverse=True):
        st.session_state.lots.pop(idx)
    st.rerun()

st.divider()
run = st.button("▶️ 計算盈虧（Run）", type="primary", use_container_width=True)

if run:
    results: list[dict[str, Any]] = []
    errors: list[str] = []

    for i, lot in enumerate(st.session_state.lots):
        raw_ticker = (lot.get("ticker") or "").strip()
        if not raw_ticker:
            errors.append(f"第 {i + 1} 筆：未填寫股票代號")
            continue
        if not lot.get("buy_price") or lot["buy_price"] <= 0:
            errors.append(f"第 {i + 1} 筆：買入價須大於 0")
            continue
        if not lot.get("quantity") or lot["quantity"] <= 0:
            errors.append(f"第 {i + 1} 筆：買入數量須大於 0")
            continue
        try:
            ticker = normalize_ticker(raw_ticker)
            buy_date = lot["buy_date"]
            if isinstance(buy_date, datetime):
                buy_date = buy_date.date()
            with st.spinner(f"正在查詢 {ticker} …"):
                data = fetch_lot_data(
                    ticker=ticker,
                    buy_date=buy_date,
                    buy_price=float(lot["buy_price"]),
                    quantity=float(lot["quantity"]),
                )
            data["row"] = i + 1
            data["input_ticker"] = raw_ticker
            results.append(data)
        except Exception as e:
            errors.append(f"第 {i + 1} 筆（{raw_ticker}）：{e}")

    for err in errors:
        st.error(err)

    if results:
        st.subheader("各持倉結果")
        rows = []
        for r in results:
            rows.append(
                {
                    "序": r["row"],
                    "代號": r["ticker"],
                    "購入日期": r["buy_date"],
                    "貨幣": r["currency"],
                    "買入價": round(r["buy_price"], 4),
                    "數量": r["quantity"],
                    "最新價": round(r["current_price"], 4),
                    "成本": round(r["cost"], 2),
                    "市值": round(r["market_value"], 2),
                    "累計股息": round(r["total_dividends"], 2),
                    "股息備註": r["div_note"],
                    "價格盈虧": round(r["price_pnl"], 2),
                    "價格盈虧%": round(r["price_pnl_pct"], 2),
                    "總盈虧(含息)": round(r["total_pnl"], 2),
                    "總盈虧%": round(r["total_pnl_pct"], 2),
                }
            )
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        for r in results:
            with st.container(border=True):
                st.markdown(
                    f"**#{r['row']} {r['ticker']}**（輸入：`{r['input_ticker']}`）· "
                    f"購入 {r['buy_date']} · 貨幣 **{r['currency']}**"
                )
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("最新價", fmt_money(r["current_price"], r["currency"]))
                m2.metric(
                    "市值 / 成本",
                    f"{fmt_money(r['market_value'], r['currency'])} / {fmt_money(r['cost'], r['currency'])}",
                )
                m3.metric(
                    "累計股息",
                    fmt_money(r["total_dividends"], r["currency"]),
                    help=r["div_note"],
                )
                m4.metric(
                    f"{color_pnl(r['price_pnl'])} 價格盈虧",
                    fmt_money(r["price_pnl"], r["currency"]),
                    fmt_pct(r["price_pnl_pct"]),
                )
                m5.metric(
                    f"{color_pnl(r['total_pnl'])} 總盈虧（含息）",
                    fmt_money(r["total_pnl"], r["currency"]),
                    fmt_pct(r["total_pnl_pct"]),
                )
                st.caption(r["div_note"])

        st.subheader("組合小計（按貨幣分開加總）")
        by_ccy: dict[str, list[dict]] = {}
        for r in results:
            by_ccy.setdefault(r["currency"], []).append(r)

        for ccy, items in by_ccy.items():
            cost_sum = sum(x["cost"] for x in items)
            mv_sum = sum(x["market_value"] for x in items)
            div_sum = sum(x["total_dividends"] for x in items)
            price_pnl_sum = sum(x["price_pnl"] for x in items)
            total_pnl_sum = sum(x["total_pnl"] for x in items)
            price_pct = (price_pnl_sum / cost_sum * 100.0) if cost_sum else 0.0
            total_pct = (total_pnl_sum / cost_sum * 100.0) if cost_sum else 0.0

            with st.container(border=True):
                st.markdown(f"**{ccy} 小計**（{len(items)} 筆）")
                s1, s2, s3, s4, s5 = st.columns(5)
                s1.metric("總成本", fmt_money(cost_sum, ccy))
                s2.metric("總市值", fmt_money(mv_sum, ccy))
                s3.metric("股息合計", fmt_money(div_sum, ccy))
                s4.metric(
                    f"{color_pnl(price_pnl_sum)} 價格盈虧",
                    fmt_money(price_pnl_sum, ccy),
                    fmt_pct(price_pct),
                )
                s5.metric(
                    f"{color_pnl(total_pnl_sum)} 總盈虧（含息）",
                    fmt_money(total_pnl_sum, ccy),
                    fmt_pct(total_pct),
                )

        if len(by_ccy) > 1:
            st.info(
                "組合同時包含不同貨幣（例如 USD 與 HKD），"
                "已按貨幣分別小計，**未進行外匯換算**。"
            )
    elif not errors:
        st.warning("沒有可計算的持倉，請先填寫至少一筆。")

st.divider()
st.caption(
    f"資料來源：Yahoo Finance（yfinance）· 查詢日期：{date.today().isoformat()} · "
    "僅供個人參考，不構成投資建議"
)
