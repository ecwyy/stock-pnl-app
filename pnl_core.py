"""股票盈虧計算核心邏輯（不含 UI）。"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import yfinance as yf


def normalize_ticker(raw: str) -> str:
    """將用戶輸入正規化為 yfinance ticker。

    美股：AAPL、MSFT → 原樣大寫
    港股：0700、700、0700.HK、9988.HK → XXXX.HK（四位補零）
    """
    s = (raw or "").strip().upper()
    if not s:
        raise ValueError("股票代號不可為空")

    if s.endswith(".HK"):
        num = s[:-3].lstrip("0") or "0"
        if not num.isdigit():
            raise ValueError(f"港股代號格式不正確：{raw}")
        return f"{int(num):04d}.HK"

    if s.isdigit():
        return f"{int(s):04d}.HK"

    return s


def detect_currency(ticker: str, info: dict | None = None) -> str:
    """從 ticker 或 yfinance info 推斷報價貨幣。"""
    if ticker.endswith(".HK"):
        return "HKD"
    if info:
        cur = info.get("currency") or info.get("financialCurrency")
        if cur:
            return str(cur).upper()
    return "USD"


def fetch_lot_data(
    ticker: str,
    buy_date: date,
    buy_price: float,
    quantity: float,
) -> dict[str, Any]:
    """取得單一持倉的現價、股息與盈虧。"""
    t = yf.Ticker(ticker)

    current_price: float | None = None
    currency = detect_currency(ticker)
    info: dict = {}

    try:
        fi = getattr(t, "fast_info", None)
        if fi is not None:
            try:
                current_price = float(fi.get("lastPrice") or fi.get("last_price") or 0) or None
            except Exception:
                pass
            try:
                c = fi.get("currency")
                if c:
                    currency = str(c).upper()
            except Exception:
                pass
    except Exception:
        pass

    if current_price is None:
        try:
            info = t.info or {}
            for key in ("currentPrice", "regularMarketPrice", "previousClose", "navPrice"):
                v = info.get(key)
                if v is not None:
                    current_price = float(v)
                    break
            if info.get("currency"):
                currency = str(info["currency"]).upper()
        except Exception:
            info = {}

    if current_price is None:
        try:
            hist = t.history(period="5d")
            if hist is not None and not hist.empty:
                current_price = float(hist["Close"].iloc[-1])
        except Exception:
            pass

    if current_price is None or current_price <= 0:
        raise ValueError(f"無法取得「{ticker}」的最新價格，請檢查代號是否正確。")

    total_div_per_share = 0.0
    div_note = ""
    try:
        divs = t.dividends
        if divs is not None and len(divs) > 0:
            idx = pd.to_datetime(divs.index)
            if getattr(idx, "tz", None) is not None:
                idx = idx.tz_convert(None)
            divs = pd.Series(divs.values, index=idx.normalize())
            buy_ts = pd.Timestamp(buy_date)
            today_ts = pd.Timestamp(date.today())
            mask = (divs.index >= buy_ts) & (divs.index <= today_ts)
            filtered = divs[mask]
            total_div_per_share = float(filtered.sum()) if len(filtered) else 0.0
            if len(filtered) == 0:
                div_note = "買入後至今無現金股息紀錄"
            else:
                div_note = f"共 {len(filtered)} 次派息"
        else:
            div_note = "無股息歷史資料，按 0 計算"
    except Exception:
        div_note = "無法取得股息資料，按 0 計算"
        total_div_per_share = 0.0

    total_dividends = total_div_per_share * quantity
    cost = buy_price * quantity
    market_value = current_price * quantity
    price_pnl = market_value - cost
    price_pnl_pct = (price_pnl / cost * 100.0) if cost else 0.0
    total_pnl = price_pnl + total_dividends
    total_pnl_pct = (total_pnl / cost * 100.0) if cost else 0.0

    return {
        "ticker": ticker,
        "buy_date": buy_date.isoformat(),
        "buy_price": buy_price,
        "quantity": quantity,
        "currency": currency,
        "current_price": current_price,
        "cost": cost,
        "market_value": market_value,
        "total_dividends": total_dividends,
        "div_note": div_note,
        "price_pnl": price_pnl,
        "price_pnl_pct": price_pnl_pct,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
    }


def fmt_money(v: float, currency: str) -> str:
    return f"{currency} {v:,.2f}"


def fmt_pct(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f}%"


def color_pnl(v: float) -> str:
    if v > 0:
        return "🟢"
    if v < 0:
        return "🔴"
    return "⚪"
