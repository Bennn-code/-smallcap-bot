from __future__ import annotations

import argparse
import time
from dataclasses import dataclass

from clients import (
    ApiError,
    fetch_bybit_klines,
    fetch_bybit_open_interest_change,
    fetch_bybit_linear_instruments,
    fetch_bybit_linear_tickers,
    fetch_cmc_listings,
    send_telegram_message,
)
from config import Settings, get_settings
from scoring import (
    Candidate,
    UBottomCandidate,
    build_candidate,
    build_debug_candidate,
    detect_u_bottom_candidate,
    format_candidate,
    format_u_bottom_candidate,
)
from scoring import (
    funding_score,
    market_cap_score,
    momentum_score,
    to_float,
    volume_score,
)
from storage import AlertStore


@dataclass(frozen=True)
class ScanStats:
    bybit_symbols: int
    cmc_rows: int
    prelim_count: int
    oi_ok_count: int
    high_count: int
    directional_count: int


@dataclass(frozen=True)
class ScanResult:
    candidates: list[Candidate]
    stats: ScanStats


@dataclass(frozen=True)
class UBottomResult:
    candidates: list[UBottomCandidate]
    scanned: int


def validate_settings(settings: Settings) -> None:
    missing = []
    if not settings.cmc_api_key:
        missing.append("CMC_API_KEY")
    if not settings.dry_run and not settings.telegram_bot_token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not settings.dry_run and not settings.telegram_chat_id:
        missing.append("TELEGRAM_CHAT_ID")

    if missing:
        raise SystemExit(f"Missing required config: {', '.join(missing)}")


def cheap_prescore(symbol: str, bybit: dict, cmc: dict) -> int | None:
    quote = cmc.get("quote", {}).get("USD", {})
    market_cap = to_float(quote.get("market_cap"))
    market_cap_points, _ = market_cap_score(market_cap)
    if market_cap_points < 0:
        return None

    cmc_volume_24h = to_float(quote.get("volume_24h"))
    bybit_turnover_24h = to_float(bybit.get("turnover24h"))
    if cmc_volume_24h < 500_000 or bybit_turnover_24h < 1_000_000:
        return None

    pct_1h = to_float(quote.get("percent_change_1h"))
    pct_24h = to_float(quote.get("percent_change_24h"))
    pct_7d = to_float(quote.get("percent_change_7d"))
    funding_rate_pct = to_float(bybit.get("fundingRate")) * 100
    volume_to_mcap_pct = (cmc_volume_24h / market_cap * 100) if market_cap else 0

    score = 10
    score += market_cap_points
    score += volume_score(volume_to_mcap_pct)
    score += momentum_score(pct_1h, pct_24h, pct_7d)
    score += funding_score(funding_rate_pct)
    if bybit_turnover_24h >= 5_000_000:
        score += 5

    return score


def scan_market(settings: Settings, max_alerts: int = 5, debug: bool = False, print_debug: bool = False) -> ScanResult:
    trading_symbols = fetch_bybit_linear_instruments()
    tickers = fetch_bybit_linear_tickers()
    cmc_by_symbol = fetch_cmc_listings(settings.cmc_api_key)

    prelim: list[tuple[int, str, dict, dict]] = []
    for symbol in sorted(trading_symbols):
        bybit = tickers.get(symbol)
        if not bybit:
            continue

        base_symbol = symbol.removesuffix("USDT")
        cmc = cmc_by_symbol.get(base_symbol)
        if not cmc:
            continue

        prescore = cheap_prescore(symbol, bybit, cmc)
        if prescore is not None and prescore >= 45:
            prelim.append((prescore, symbol, bybit, cmc))

    prelim.sort(key=lambda item: item[0], reverse=True)

    candidates: list[Candidate] = []
    oi_ok_count = 0
    for _, symbol, bybit, cmc in prelim[:80]:
        try:
            oi_1h_pct = fetch_bybit_open_interest_change(symbol, "1h")
            time.sleep(0.08)
            oi_4h_pct = fetch_bybit_open_interest_change(symbol, "4h")
            time.sleep(0.08)
        except ApiError:
            oi_1h_pct = None
            oi_4h_pct = None
        if oi_1h_pct is not None or oi_4h_pct is not None:
            oi_ok_count += 1

        if debug:
            candidate = build_debug_candidate(symbol, bybit, cmc, oi_1h_pct, oi_4h_pct)
        else:
            candidate = build_candidate(symbol, bybit, cmc, oi_1h_pct, oi_4h_pct)
        if candidate:
            candidates.append(candidate)

    candidates.sort(key=lambda item: item.score, reverse=True)
    stats = ScanStats(
        bybit_symbols=len(trading_symbols),
        cmc_rows=len(cmc_by_symbol),
        prelim_count=len(prelim),
        oi_ok_count=oi_ok_count,
        high_count=sum(1 for item in candidates if item.level == "HIGH"),
        directional_count=sum(1 for item in candidates if item.direction in {"LONG", "SHORT", "WATCH-LONG", "WATCH-SHORT"}),
    )

    if print_debug:
        print("DEBUG 掃描摘要")
        print(f"Bybit USDT可交易合約數：{stats.bybit_symbols}")
        print(f"CMC資料筆數：{stats.cmc_rows}")
        print(f"通過便宜預篩：{stats.prelim_count}")
        print(f"有OI資料：{stats.oi_ok_count}")
        print(f"HIGH({settings.high_alert_score}分以上)：{stats.high_count}")
        print(f"LONG/SHORT：{stats.directional_count}")
        print("")
    return ScanResult(candidates=candidates[:max_alerts], stats=stats)


def scan_once(settings: Settings, max_alerts: int = 5, debug: bool = False) -> list[Candidate]:
    return scan_market(settings, max_alerts=max_alerts, debug=debug, print_debug=debug).candidates


def scan_u_bottom(settings: Settings, max_alerts: int = 5) -> UBottomResult:
    trading_symbols = fetch_bybit_linear_instruments()
    tickers = fetch_bybit_linear_tickers()
    cmc_by_symbol = fetch_cmc_listings(settings.cmc_api_key)

    prelim: list[tuple[int, str, dict]] = []
    for symbol in sorted(trading_symbols):
        bybit = tickers.get(symbol)
        if not bybit:
            continue
        cmc = cmc_by_symbol.get(symbol.removesuffix("USDT"))
        if not cmc:
            continue
        prescore = cheap_prescore(symbol, bybit, cmc)
        if prescore is not None and prescore >= 35:
            prelim.append((prescore, symbol, cmc))

    prelim.sort(key=lambda item: item[0], reverse=True)

    candidates: list[UBottomCandidate] = []
    scanned = 0
    for _, symbol, cmc in prelim[:120]:
        try:
            daily_klines = fetch_bybit_klines(symbol, "D", limit=120)
            time.sleep(0.08)
            h4_klines = fetch_bybit_klines(symbol, "240", limit=120)
            time.sleep(0.08)
        except ApiError:
            continue

        scanned += 1
        candidate = detect_u_bottom_candidate(symbol, cmc, daily_klines, h4_klines)
        if candidate:
            candidates.append(candidate)

    candidates.sort(key=lambda item: item.score, reverse=True)
    return UBottomResult(candidates=candidates[:max_alerts], scanned=scanned)


def format_daily_summary(result: ScanResult, settings: Settings) -> str:
    lines = [
        "📋 今日小幣雷達摘要",
        "",
        f"Bybit合約：{result.stats.bybit_symbols}",
        f"CMC資料：{result.stats.cmc_rows}",
        f"通過初篩：{result.stats.prelim_count}",
        f"有OI資料：{result.stats.oi_ok_count}",
        f"HIGH({settings.high_alert_score}分以上)：{result.stats.high_count}",
        f"LONG/SHORT：{result.stats.directional_count}",
        "",
        "最接近標的：",
    ]

    if not result.candidates:
        lines.append("目前沒有接近條件的幣。")
        return "\n".join(lines)

    for index, candidate in enumerate(result.candidates[:5], start=1):
        oi_4h = "N/A" if candidate.oi_4h_pct is None else f"{candidate.oi_4h_pct:+.1f}%"
        lines.append(
            f"{index}. {candidate.symbol}｜{candidate.score}｜{candidate.direction}｜"
            f"{candidate.market_cap_bucket}｜OI4h {oi_4h}｜24h {candidate.pct_24h:+.1f}%"
        )

    return "\n".join(lines)


def format_watch_summary(result: ScanResult, settings: Settings) -> str:
    lines = [
        "🔎 小幣雷達觀察摘要（6小時）",
        "",
        "這不是正式推薦，是用來確認系統正常掃描，並觀察是否有標的接近條件。",
        "",
        f"合約數：{result.stats.bybit_symbols}",
        f"CMC資料：{result.stats.cmc_rows}",
        f"通過初篩：{result.stats.prelim_count}",
        f"有OI資料：{result.stats.oi_ok_count}",
        f"HIGH({settings.high_alert_score}分以上)：{result.stats.high_count}",
        f"LONG/SHORT：{result.stats.directional_count}",
        "",
        "最接近標的：",
    ]

    if not result.candidates:
        lines.append("目前沒有接近條件的幣。")
        return "\n".join(lines)

    for index, candidate in enumerate(result.candidates[:max(1, min(10, len(result.candidates)))], start=1):
        oi_1h = "N/A" if candidate.oi_1h_pct is None else f"{candidate.oi_1h_pct:+.1f}%"
        oi_4h = "N/A" if candidate.oi_4h_pct is None else f"{candidate.oi_4h_pct:+.1f}%"
        lines.append(
            f"{index}. {candidate.symbol}｜{candidate.score}｜{candidate.direction}｜"
            f"{candidate.market_cap_bucket}｜1h {candidate.pct_1h:+.1f}%｜"
            f"24h {candidate.pct_24h:+.1f}%｜OI1h {oi_1h}｜OI4h {oi_4h}"
        )

    return "\n".join(lines)


def format_test_message(settings: Settings) -> str:
    return "\n".join(
        [
            "✅ smallcap-bot 更新完成測試",
            "",
            "新版規則已載入：",
            f"• HIGH：{settings.high_alert_score}分以上，每天最多 {settings.high_daily_limit} 則",
            f"• EARLY：{settings.early_alert_score}分以上，每天最多 {settings.early_daily_limit} 則",
            f"• 同幣同方向同等級 cooldown：{settings.cooldown_hours} 小時",
            "• EARLY 升 HIGH 可以再次推送",
            f"• U型底：三天掃一次，最多 {settings.u_bottom_limit} 則；沒有候選就不推送",
            "",
            "版面預覽：",
            "🟢🚀 小幣合約機會 | HIGH | LONG",
            "分數：████████░░ 82/100",
            "📊 價格動能 / 📈 合約量能 / 🏷 基本資料會分段顯示",
        ]
    )


def run(
    settings: Settings,
    once: bool,
    max_alerts: int,
    debug: bool,
    summary: bool,
    watch_summary: bool,
    u_bottom: bool,
    test_message: bool,
) -> None:
    validate_settings(settings)
    store = AlertStore(settings.sqlite_path)

    while True:
        if test_message:
            message = format_test_message(settings)
            if settings.dry_run:
                print(message)
            else:
                send_telegram_message(
                    settings.telegram_bot_token,
                    settings.telegram_chat_id,
                    message,
                    settings.telegram_thread_id,
                )
            return

        if u_bottom:
            result = scan_u_bottom(settings, max_alerts=min(max_alerts, settings.u_bottom_limit))
            sent_count = 0
            for candidate in result.candidates:
                if not settings.dry_run and not store.can_alert(
                    candidate.symbol,
                    "LONG",
                    "U_BOTTOM",
                    settings.u_bottom_cooldown_days * 24,
                ):
                    continue

                message = format_u_bottom_candidate(candidate)
                if settings.dry_run:
                    print("=" * 60)
                    print(message)
                else:
                    send_telegram_message(
                        settings.telegram_bot_token,
                        settings.telegram_chat_id,
                        message,
                        settings.telegram_thread_id,
                    )
                    store.record(candidate.symbol, "LONG", "U_BOTTOM", candidate.score)
                    sent_count += 1

            if settings.dry_run and not result.candidates:
                print(f"U型底掃描完成：檢查 {result.scanned} 個標的，目前沒有候選。")

            if once:
                return

            time.sleep(settings.scan_interval_seconds)
            continue

        if watch_summary:
            result = scan_market(settings, max_alerts=max_alerts, debug=True, print_debug=False)
            message = format_watch_summary(result, settings)
            if settings.dry_run:
                print(message)
            else:
                send_telegram_message(
                    settings.telegram_bot_token,
                    settings.telegram_chat_id,
                    message,
                    settings.telegram_thread_id,
                )

            if once:
                return

            time.sleep(settings.scan_interval_seconds)
            continue

        if summary:
            result = scan_market(settings, max_alerts=max_alerts, debug=True, print_debug=False)
            message = format_daily_summary(result, settings)
            if settings.dry_run:
                print(message)
            elif not store.summary_sent_today():
                send_telegram_message(
                    settings.telegram_bot_token,
                    settings.telegram_chat_id,
                    message,
                    settings.telegram_thread_id,
                )
                store.record_summary_sent()

            if once:
                return

            time.sleep(settings.scan_interval_seconds)
            continue

        candidates = scan_once(settings, max_alerts=max_alerts, debug=debug)
        high_sent_today = store.alerts_sent_today("HIGH")
        early_sent_today = store.alerts_sent_today("EARLY")

        for candidate in candidates:
            if not debug and candidate.level not in {"HIGH", "EARLY"}:
                continue
            if not debug and candidate.level == "WATCH" and not settings.send_watch_alerts:
                continue
            if not settings.dry_run and candidate.level == "HIGH" and high_sent_today >= settings.high_daily_limit:
                continue
            if not settings.dry_run and candidate.level == "EARLY" and early_sent_today >= settings.early_daily_limit:
                continue
            if not settings.dry_run and not store.can_alert(
                candidate.symbol,
                candidate.direction,
                candidate.level,
                settings.cooldown_hours,
            ):
                continue

            message = format_candidate(candidate)
            if settings.dry_run:
                print("=" * 60)
                print(message)
            else:
                send_telegram_message(
                    settings.telegram_bot_token,
                    settings.telegram_chat_id,
                    message,
                    settings.telegram_thread_id,
                )
                store.record(candidate.symbol, candidate.direction, candidate.level, candidate.score)
                if candidate.level == "HIGH":
                    high_sent_today += 1
                elif candidate.level == "EARLY":
                    early_sent_today += 1

        if once:
            return

        time.sleep(settings.scan_interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bybit + CMC small-cap futures scanner")
    parser.add_argument("--once", action="store_true", help="Run one scan and exit")
    parser.add_argument("--max-alerts", type=int, default=5, help="Max candidates per scan")
    parser.add_argument("--debug", action="store_true", help="Show diagnostic candidates without TG filtering")
    parser.add_argument("--summary", action="store_true", help="Print or send a daily radar summary")
    parser.add_argument("--watch-summary", action="store_true", help="Send an observation summary every time it runs")
    parser.add_argument("--u-bottom", action="store_true", help="Scan daily U-bottom reversals with 4h confirmation")
    parser.add_argument("--test-message", action="store_true", help="Send a Telegram update test message")
    args = parser.parse_args()

    run(
        get_settings(),
        once=args.once,
        max_alerts=args.max_alerts,
        debug=args.debug,
        summary=args.summary,
        watch_summary=args.watch_summary,
        u_bottom=args.u_bottom,
        test_message=args.test_message,
    )


if __name__ == "__main__":
    main()
