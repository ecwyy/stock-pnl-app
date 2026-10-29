"""股票盈虧計算核心邏輯（不含 UI）。"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from typing import Any

import pandas as pd
import yfinance as yf


def normalize_ticker(raw: str) -> str:
    """將用戶輸入正規化為 yfinance ticker。

    美股：AAPL、MSFT、O、JAAA → 原樣大寫
    港股：0700、700、823、0700.HK、9988.HK → XXXX.HK（四位補零）
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


def _parse_chart_payload(payload: dict) -> tuple[float | None, str | None]:
    results = (payload.get("chart") or {}).get("result") or []
    if not results:
        return None, None

    meta = results[0].get("meta") or {}
    price = meta.get("regularMarketPrice")
    if price is None:
        price = meta.get("fulldayPrice") or meta.get("chartPreviousClose")
    if price is None:
        quotes = (results[0].get("indicators") or {}).get("quote") or []
        closes = (quotes[0].get("close") if quotes else None) or []
        closes = [c for c in closes if c is not None]
        if closes:
            price = closes[-1]

    currency = meta.get("currency")
    try:
        price_f = float(price) if price is not None else None
    except (TypeError, ValueError):
        return None, None
    if price_f is None or price_f <= 0:
        return None, None
    return price_f, (str(currency).upper() if currency else None)


def _chart_urls(ticker: str) -> list[str]:
    encoded = urllib.parse.quote(ticker, safe=".")
    return [
        f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?interval=1d&range=5d",
        f"https://query2.finance.yahoo.com/v8/finance/chart/{encoded}?interval=1d&range=5d",
    ]


_CHART_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
}


def _price_from_yahoo_chart(ticker: str) -> tuple[float | None, str | None]:
    """直接打 Yahoo chart API 取最新價（優先於 yfinance，Cloud 較穩）。"""
    urls = _chart_urls(ticker)

    # curl_cffi 模擬瀏覽器 TLS，對資料中心 IP（例如 Streamlit Cloud）較不易被擋
    try:
        from curl_cffi import requests as creq

        for url in urls:
            try:
                resp = creq.get(
                    url,
                    headers=_CHART_HEADERS,
                    impersonate="chrome",
                    timeout=15,
                )
                if resp.status_code != 200:
                    continue
                price, cur = _parse_chart_payload(resp.json())
                if price is not None:
                    return price, cur
            except Exception:
                continue
    except ImportError:
        pass

    for url in urls:
        req = urllib.request.Request(url, headers=_CHART_HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode())
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
            OSError,
        ):
            continue
        price, cur = _parse_chart_payload(payload)
        if price is not None:
            return price, cur

    return None, None


def _price_from_fast_info(ticker_obj: Any) -> tuple[float | None, str | None]:
    try:
        fi = getattr(ticker_obj, "fast_info", None)
        if fi is None:
            return None, None
        price = None
        currency = None
        try:
            price = fi.get("lastPrice") or fi.get("last_price")
        except Exception:
            price = getattr(fi, "last_price", None) or getattr(fi, "lastPrice", None)
        try:
            currency = fi.get("currency")
        except Exception:
            currency = getattr(fi, "currency", None)
        try:
            price_f = float(price) if price is not None else None
        except (TypeError, ValueError):
            price_f = None
        if price_f is not None and price_f <= 0:
            price_f = None
        return price_f, (str(currency).upper() if currency else None)
    except Exception:
        return None, None


def _price_from_info(ticker_obj: Any) -> tuple[float | None, str | None, dict]:
    info: dict = {}
    try:
        info = ticker_obj.info or {}
    except Exception:
        return None, None, {}
    price = None
    for key in ("currentPrice", "regularMarketPrice", "previousClose", "navPrice"):
        v = info.get(key)
        if v is not None:
            try:
                price = float(v)
                if price > 0:
                    break
            except (TypeError, ValueError):
                price = None
            else:
                if price and price > 0:
                    break
                price = None
    currency = info.get("currency")
    return price, (str(currency).upper() if currency else None), info


def _price_from_history(ticker_obj: Any) -> float | None:
    try:
        hist = ticker_obj.history(period="5d")
        if hist is not None and not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return None


def fetch_lot_data(
    ticker: str,
    buy_date: date,
    buy_price: float,
    quantity: float,
) -> dict[str, Any]:
    """取得單一持倉的現價、股息與盈虧。"""
    current_price: float | None = None
    currency = detect_currency(ticker)
    info: dict = {}

    # 先打 Yahoo chart（無需 crumb；Streamlit Cloud 上比 yfinance 穩）
    price, cur = _price_from_yahoo_chart(ticker)
    if price is not None and price > 0:
        current_price = price
    if cur:
        currency = cur

    t = yf.Ticker(ticker)

    if current_price is None:
        price, cur = _price_from_fast_info(t)
        if price is not None:
            current_price = price
        if cur:
            currency = cur

    if current_price is None:
        price, cur, info = _price_from_info(t)
        if price is not None:
            current_price = price
        if cur:
            currency = cur

    if current_price is None:
        price = _price_from_history(t)
        if price is not None and price > 0:
            current_price = price

    if current_price is None or current_price <= 0:
        # 再試一次 chart（偶發限流）
        price, cur = _price_from_yahoo_chart(ticker)
        if price is not None and price > 0:
            current_price = price
        if cur:
            currency = cur

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
