"""煙霧測試：確認可取得美股與港股價格及股息。"""

from __future__ import annotations

from datetime import date

from pnl_core import fetch_lot_data, normalize_ticker


def check(label: str, raw: str, buy_date: date, buy_price: float, qty: float) -> None:
    ticker = normalize_ticker(raw)
    print(f"\n=== {label}: 輸入={raw!r} → {ticker} ===")
    data = fetch_lot_data(ticker, buy_date, buy_price, qty)
    assert data["current_price"] > 0, f"{ticker} price not positive: {data['current_price']}"
    print(f"  貨幣: {data['currency']}")
    print(f"  最新價: {data['current_price']:.4f}")
    print(f"  成本: {data['cost']:.2f}")
    print(f"  市值: {data['market_value']:.2f}")
    print(f"  累計股息: {data['total_dividends']:.4f} ({data['div_note']})")
    print(f"  價格盈虧: {data['price_pnl']:.2f} ({data['price_pnl_pct']:.2f}%)")
    print(f"  總盈虧(含息): {data['total_pnl']:.2f} ({data['total_pnl_pct']:.2f}%)")


def main() -> None:
    assert normalize_ticker("700") == "0700.HK"
    assert normalize_ticker("0700") == "0700.HK"
    assert normalize_ticker("0700.HK") == "0700.HK"
    assert normalize_ticker("823") == "0823.HK"
    assert normalize_ticker("0823.HK") == "0823.HK"
    assert normalize_ticker("aapl") == "AAPL"
    assert normalize_ticker("O") == "O"
    assert normalize_ticker("jaaa") == "JAAA"
    assert normalize_ticker("3466") == "3466.HK"
    print("normalize_ticker OK")

    check("美股 AAPL", "AAPL", date(2023, 1, 3), 130.0, 10)
    check("港股 騰訊", "0700", date(2023, 1, 3), 350.0, 100)
    check("港股 ETF 3466", "3466", date(2025, 5, 1), 18.0, 400)
    check("港股 Link REIT 823", "823", date(2024, 1, 2), 35.0, 100)
    check("美股 Realty Income O", "O", date(2024, 1, 2), 50.0, 20)
    check("美股 ETF JAAA", "JAAA", date(2024, 6, 1), 50.0, 50)
    print("\n煙霧測試完成。")


if __name__ == "__main__":
    main()
