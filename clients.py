from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from typing import Any


class ApiError(RuntimeError):
    pass


BYBIT_BASE_URL = os.environ.get("BYBIT_BASE_URL", "https://api.bytick.com").rstrip("/")
BINGX_SWAP_BASE_URL = os.environ.get("BINGX_SWAP_BASE_URL", "https://open-api.bingx.com").rstrip("/")
BINANCE_FAPI_BASE_URL = os.environ.get("BINANCE_FAPI_BASE_URL", "https://fapi.binance.com").rstrip("/")


def request_json(
    url: str,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    if params:
        query = urllib.parse.urlencode(params)
        url = f"{url}?{query}"

    request_headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 smallcap-bot/1.0",
    }
    if headers:
        request_headers.update(headers)

    req = urllib.request.Request(url, headers=request_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)
    except Exception as exc:
        raise ApiError(f"request failed: {url}: {exc}") from exc


def post_json(
    url: str,
    payload: dict[str, Any],
    timeout: int = 20,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)
    except Exception as exc:
        raise ApiError(f"post failed: {url}: {exc}") from exc


def _bingx_symbol(symbol: str) -> str:
    if "-" in symbol:
        return symbol
    return symbol.removesuffix("USDT") + "-USDT"


def _normalize_bingx_symbol(symbol: str) -> str:
    return symbol.replace("-", "")


def _bingx_request(path: str, params: dict[str, Any] | None = None) -> Any:
    request_params = dict(params or {})
    request_params.setdefault("timestamp", str(int(time.time() * 1000)))
    data = request_json(f"{BINGX_SWAP_BASE_URL}{path}", params=request_params)
    if data.get("code") not in (0, "0", None):
        raise ApiError(f"bingx error: {data}")
    return data.get("data")


def fetch_bingx_linear_tickers() -> dict[str, dict[str, Any]]:
    rows = _bingx_request("/openApi/swap/v2/quote/ticker")
    funding_rows = _bingx_request("/openApi/swap/v2/quote/premiumIndex")
    if isinstance(rows, dict):
        rows = [rows]
    if isinstance(funding_rows, dict):
        funding_rows = [funding_rows]

    funding_by_symbol = {
        _normalize_bingx_symbol(row.get("symbol", "")): row.get("lastFundingRate", "0")
        for row in funding_rows or []
        if isinstance(row, dict)
    }

    tickers: dict[str, dict[str, Any]] = {}
    for item in rows or []:
        if not isinstance(item, dict):
            continue
        symbol = _normalize_bingx_symbol(item.get("symbol", ""))
        if not symbol.endswith("USDT"):
            continue
        tickers[symbol] = {
            "symbol": symbol,
            "turnover24h": item.get("quoteVolume", "0"),
            "fundingRate": funding_by_symbol.get(symbol, "0"),
            "lastPrice": item.get("lastPrice", "0"),
            "highPrice24h": item.get("highPrice", "0"),
            "lowPrice24h": item.get("lowPrice", "0"),
        }
    return tickers


def fetch_bingx_linear_instruments() -> set[str]:
    rows = _bingx_request("/openApi/swap/v2/quote/contracts")
    symbols: set[str] = set()
    for item in rows or []:
        if not isinstance(item, dict):
            continue
        if (
            item.get("currency") == "USDT"
            and item.get("status") == 1
            and item.get("apiStateOpen") == "true"
            and item.get("apiStateClose") == "true"
        ):
            symbols.add(_normalize_bingx_symbol(item.get("symbol", "")))
    return symbols


def fetch_bingx_open_interest_change(symbol: str, interval: str, limit: int = 2) -> float | None:
    # BingX public swap API exposes current open interest, not a short OI history.
    # Keep the exchange priority for symbols/tickers, then use Binance as the next
    # source for the OI-change signal this scanner needs.
    return fetch_binance_open_interest_change(symbol, interval, limit)


def fetch_binance_linear_tickers() -> dict[str, dict[str, Any]]:
    rows = request_json(f"{BINANCE_FAPI_BASE_URL}/fapi/v1/ticker/24hr")
    funding_rows = request_json(f"{BINANCE_FAPI_BASE_URL}/fapi/v1/premiumIndex")
    funding_by_symbol = {
        row.get("symbol", ""): row.get("lastFundingRate", "0")
        for row in funding_rows
        if isinstance(row, dict)
    }

    tickers: dict[str, dict[str, Any]] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        symbol = item.get("symbol", "")
        if not symbol.endswith("USDT"):
            continue
        tickers[symbol] = {
            "symbol": symbol,
            "turnover24h": item.get("quoteVolume", "0"),
            "fundingRate": funding_by_symbol.get(symbol, "0"),
            "lastPrice": item.get("lastPrice", "0"),
            "highPrice24h": item.get("highPrice", "0"),
            "lowPrice24h": item.get("lowPrice", "0"),
        }
    return tickers


def fetch_binance_linear_instruments() -> set[str]:
    data = request_json(f"{BINANCE_FAPI_BASE_URL}/fapi/v1/exchangeInfo")
    symbols: set[str] = set()
    for item in data.get("symbols", []):
        if (
            item.get("quoteAsset") == "USDT"
            and item.get("contractType") == "PERPETUAL"
            and item.get("status") == "TRADING"
        ):
            symbols.add(item.get("symbol", ""))
    return symbols


def fetch_binance_open_interest_change(symbol: str, period: str, limit: int = 2) -> float | None:
    rows = request_json(
        f"{BINANCE_FAPI_BASE_URL}/futures/data/openInterestHist",
        params={"symbol": symbol, "period": period, "limit": str(limit)},
    )
    if not isinstance(rows, list) or len(rows) < 2:
        return None

    rows = sorted(rows, key=lambda row: int(row.get("timestamp", 0)))
    first = float(rows[0].get("sumOpenInterestValue") or rows[0].get("sumOpenInterest") or 0)
    last = float(rows[-1].get("sumOpenInterestValue") or rows[-1].get("sumOpenInterest") or 0)
    if first <= 0:
        return None

    return (last - first) / first * 100


def fetch_bybit_linear_tickers() -> dict[str, dict[str, Any]]:
    try:
        data = request_json(
            f"{BYBIT_BASE_URL}/v5/market/tickers",
            params={"category": "linear"},
        )
    except ApiError:
        try:
            return fetch_bingx_linear_tickers()
        except ApiError:
            return fetch_binance_linear_tickers()

    if data.get("retCode") != 0:
        raise ApiError(f"bybit tickers error: {data}")

    tickers: dict[str, dict[str, Any]] = {}
    for item in data.get("result", {}).get("list", []):
        symbol = item.get("symbol", "")
        if symbol.endswith("USDT"):
            tickers[symbol] = item
    return tickers


def fetch_bybit_linear_instruments() -> set[str]:
    symbols: set[str] = set()
    cursor = ""

    while True:
        params = {"category": "linear", "limit": "1000"}
        if cursor:
            params["cursor"] = cursor

        try:
            data = request_json(
                f"{BYBIT_BASE_URL}/v5/market/instruments-info",
                params=params,
            )
        except ApiError:
            try:
                return fetch_bingx_linear_instruments()
            except ApiError:
                return fetch_binance_linear_instruments()

        if data.get("retCode") != 0:
            raise ApiError(f"bybit instruments error: {data}")

        result = data.get("result", {})
        for item in result.get("list", []):
            if item.get("quoteCoin") == "USDT" and item.get("status") == "Trading":
                symbols.add(item.get("symbol", ""))

        cursor = result.get("nextPageCursor") or ""
        if not cursor:
            return symbols

        time.sleep(0.15)


def fetch_bybit_open_interest_change(symbol: str, interval: str, limit: int = 2) -> float | None:
    try:
        data = request_json(
            f"{BYBIT_BASE_URL}/v5/market/open-interest",
            params={
                "category": "linear",
                "symbol": symbol,
                "intervalTime": interval,
                "limit": str(limit),
            },
        )
    except ApiError:
        try:
            return fetch_bingx_open_interest_change(symbol, interval, limit)
        except ApiError:
            return fetch_binance_open_interest_change(symbol, interval, limit)

    if data.get("retCode") != 0:
        raise ApiError(f"bybit open interest error for {symbol}: {data}")

    rows = data.get("result", {}).get("list", [])
    if len(rows) < 2:
        return None

    rows = sorted(rows, key=lambda row: int(row.get("timestamp", 0)))
    first = float(rows[0].get("openInterest") or 0)
    last = float(rows[-1].get("openInterest") or 0)
    if first <= 0:
        return None

    return (last - first) / first * 100


def fetch_cmc_listings(api_key: str, limit: int = 5000) -> dict[str, dict[str, Any]]:
    data = request_json(
        "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest",
        headers={"X-CMC_PRO_API_KEY": api_key, "Accept": "application/json"},
        params={
            "start": "1",
            "limit": str(limit),
            "convert": "USD",
            "sort": "market_cap",
            "sort_dir": "desc",
            "aux": "cmc_rank,circulating_supply",
        },
    )

    status = data.get("status", {})
    if status.get("error_code") not in (0, None):
        raise ApiError(f"cmc listings error: {status}")

    by_symbol: dict[str, dict[str, Any]] = {}
    for item in data.get("data", []):
        symbol = item.get("symbol", "").upper()
        if symbol and symbol not in by_symbol:
            by_symbol[symbol] = item
    return by_symbol


def send_telegram_message(
    bot_token: str,
    chat_id: str,
    text: str,
    thread_id: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if thread_id is not None:
        payload["message_thread_id"] = thread_id

    return post_json(f"https://api.telegram.org/bot{bot_token}/sendMessage", payload)
