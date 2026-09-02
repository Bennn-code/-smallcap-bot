from __future__ import annotations

from dataclasses import dataclass
from typing import Any

HIGH_ALERT_SCORE = 75
EARLY_ALERT_SCORE = 70
WATCH_SCORE = 60


@dataclass(frozen=True)
class Candidate:
    symbol: str
    base_symbol: str
    name: str
    cmc_rank: int | None
    market_cap: float
    market_cap_bucket: str
    cmc_volume_24h: float
    bybit_turnover_24h: float
    volume_to_mcap_pct: float
    pct_1h: float
    pct_24h: float
    pct_7d: float
    oi_1h_pct: float | None
    oi_4h_pct: float | None
    funding_rate_pct: float
    last_price: float
    high_24h: float
    low_24h: float
    score: int
    level: str
    direction: str
    direction_icon: str
    confidence: str
    tags: list[str]
    reasons: list[str]


@dataclass(frozen=True)
class UBottomCandidate:
    symbol: str
    base_symbol: str
    name: str
    cmc_rank: int | None
    market_cap: float
    market_cap_bucket: str
    score: int
    last_price: float
    low_90d: float
    high_90d: float
    bounce_from_low_pct: float
    distance_to_30d_high_pct: float
    daily_volume_ratio: float
    h4_volume_ratio: float
    h4_trend_pct: float
    tags: list[str]
    reasons: list[str]


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def market_cap_score(market_cap: float) -> tuple[int, str]:
    if market_cap < 10_000_000:
        return -999, "< 10M"
    if market_cap < 100_000_000:
        return 6, "10M - 100M"
    if market_cap < 300_000_000:
        return 12, "100M - 300M"
    if market_cap < 1_000_000_000:
        return 20, "300M - 1B"
    if market_cap < 3_000_000_000:
        return 16, "1B - 3B"
    if market_cap < 10_000_000_000:
        return 8, "3B - 10B"
    return 2, "> 10B"


def volume_score(volume_to_mcap_pct: float) -> int:
    if volume_to_mcap_pct >= 30:
        return 20
    if volume_to_mcap_pct >= 15:
        return 17
    if volume_to_mcap_pct >= 8:
        return 13
    if volume_to_mcap_pct >= 3:
        return 6
    return 0


def momentum_score(pct_1h: float, pct_24h: float, pct_7d: float) -> int:
    score = 0

    if 2 <= pct_1h <= 5:
        score += 6
    elif 5 < pct_1h <= 10:
        score += 10
    elif pct_1h > 10:
        score += 6

    if 5 <= pct_24h <= 12:
        score += 8
    elif 12 < pct_24h <= 30:
        score += 12
    elif pct_24h > 30:
        score += 6

    if 0 <= pct_7d <= 80:
        score += 3
    elif 80 < pct_7d <= 200:
        score += 1

    return score


def oi_score(oi_1h_pct: float | None, oi_4h_pct: float | None) -> int:
    score = 0
    if oi_4h_pct is not None:
        if oi_4h_pct >= 30:
            score += 18
        elif oi_4h_pct >= 15:
            score += 12
        elif oi_4h_pct >= 5:
            score += 5

    if oi_1h_pct is not None:
        if oi_1h_pct >= 12:
            score += 8
        elif oi_1h_pct >= 5:
            score += 6
        elif oi_1h_pct >= 1:
            score += 2

    return min(score, 20)


def funding_score(funding_rate_pct: float) -> int:
    if -0.05 <= funding_rate_pct <= 0.05:
        return 10
    if -0.08 <= funding_rate_pct <= 0.08:
        return 7
    if -0.12 <= funding_rate_pct <= 0.12:
        return 4
    return 0


def risk_penalty(
    pct_1h: float,
    pct_24h: float,
    pct_7d: float,
    volume_to_mcap_pct: float,
    funding_rate_pct: float,
    oi_1h_pct: float | None,
    oi_4h_pct: float | None,
) -> int:
    penalty = 0
    if pct_7d > 200:
        penalty -= 15
    if pct_24h > 60:
        penalty -= 10
    if pct_1h > 15:
        penalty -= 10
    if volume_to_mcap_pct > 100:
        penalty -= 10
    if abs(funding_rate_pct) > 0.15:
        penalty -= 10
    if oi_4h_pct is not None and oi_4h_pct > 80:
        penalty -= 8
    if oi_1h_pct is not None and oi_1h_pct > 35:
        penalty -= 8
    return penalty


def direction_for(
    market_cap: float,
    pct_1h: float,
    pct_24h: float,
    pct_7d: float,
    volume_to_mcap_pct: float,
    funding_rate_pct: float,
    oi_1h_pct: float | None,
    oi_4h_pct: float | None,
    last_price: float,
    high_24h: float,
) -> tuple[str, str, str, list[str], list[str]]:
    reasons: list[str] = []
    tags: list[str] = []
    near_high = high_24h > 0 and last_price >= high_24h * 0.92
    overheated = pct_7d > 150 or pct_24h > 40 or funding_rate_pct > 0.12
    oi_rising = (oi_4h_pct is not None and oi_4h_pct >= 15) or (oi_1h_pct is not None and oi_1h_pct >= 5)
    funding_healthy = -0.05 <= funding_rate_pct <= 0.08

    if oi_rising:
        tags.append("OI放大")
    if funding_healthy:
        tags.append("資金健康")

    if pct_1h >= 0 and pct_24h >= 3 and volume_to_mcap_pct >= 8 and oi_rising and funding_healthy and not overheated:
        reasons.extend(["OI放大", "資金健康", "短線溫和啟動"])
        tags.append("上車準備")
        if market_cap < 300_000_000 and pct_7d < 80 and volume_to_mcap_pct >= 12:
            return "LONG", "🌱", "中高", tags, reasons + ["低市值啟動"]
        if pct_24h >= 20 and volume_to_mcap_pct >= 20 and pct_1h <= 15:
            return "LONG", "🚀", "中", tags, reasons + ["強勢放量"]
        return "LONG", "📈", "高" if near_high else "中高", tags, reasons

    if overheated and pct_1h <= -2 and oi_rising:
        reasons.extend(["過熱後轉弱", "高位回落", "OI仍在增加"])
        tags.append("過熱轉弱")
        if funding_rate_pct > 0.12:
            reasons.append("資金費率偏高")
        return "SHORT", "🔥", "中", tags, reasons

    if pct_1h <= -2 and pct_24h <= 5 and oi_rising:
        tags.append("短線轉弱")
        return "SHORT", "📉", "中", tags, ["短線轉弱", "價格動能偏空", "OI增加"]

    if funding_rate_pct > 0.15 and pct_24h > 30:
        tags.append("高風險")
        return "SHORT", "⚠️", "低", tags, ["資金費率過高", "可能有多頭擁擠"]

    if pct_1h * pct_24h < 0:
        return "WATCH", "⚖️", "低", tags, ["多空訊號衝突"]

    return "WATCH", "⏳", "低", tags, ["等待方向確認"]


def level_for(score: int, direction: str) -> str:
    if score >= HIGH_ALERT_SCORE:
        return "HIGH"
    if score >= EARLY_ALERT_SCORE:
        return "EARLY"
    if score >= WATCH_SCORE:
        return "WATCH"
    return "DEBUG"


def build_debug_candidate(
    symbol: str,
    bybit: dict[str, Any],
    cmc: dict[str, Any],
    oi_1h_pct: float | None = None,
    oi_4h_pct: float | None = None,
) -> Candidate | None:
    candidate = build_candidate(symbol, bybit, cmc, oi_1h_pct, oi_4h_pct)
    if candidate:
        return candidate

    quote = cmc.get("quote", {}).get("USD", {})
    market_cap = to_float(quote.get("market_cap"))
    market_cap_points, bucket = market_cap_score(market_cap)
    if market_cap_points < 0:
        return None

    cmc_volume_24h = to_float(quote.get("volume_24h"))
    bybit_turnover_24h = to_float(bybit.get("turnover24h"))
    pct_1h = to_float(quote.get("percent_change_1h"))
    pct_24h = to_float(quote.get("percent_change_24h"))
    pct_7d = to_float(quote.get("percent_change_7d"))
    funding_rate_pct = to_float(bybit.get("fundingRate")) * 100
    last_price = to_float(bybit.get("lastPrice"))
    high_24h = to_float(bybit.get("highPrice24h"))
    low_24h = to_float(bybit.get("lowPrice24h"))
    volume_to_mcap_pct = (cmc_volume_24h / market_cap * 100) if market_cap else 0

    score = 10
    score += market_cap_points
    score += volume_score(volume_to_mcap_pct)
    score += momentum_score(pct_1h, pct_24h, pct_7d)
    score += oi_score(oi_1h_pct, oi_4h_pct)
    score += funding_score(funding_rate_pct)
    if bybit_turnover_24h >= 5_000_000:
        score += 5
    score += risk_penalty(pct_1h, pct_24h, pct_7d, volume_to_mcap_pct, funding_rate_pct, oi_1h_pct, oi_4h_pct)
    score = max(0, min(100, int(score)))

    direction, icon, confidence, tags, reasons = direction_for(
        market_cap,
        pct_1h,
        pct_24h,
        pct_7d,
        volume_to_mcap_pct,
        funding_rate_pct,
        oi_1h_pct,
        oi_4h_pct,
        last_price,
        high_24h,
    )

    fail_reasons: list[str] = []
    if cmc_volume_24h < 500_000:
        fail_reasons.append("CMC成交量低於500K")
    if bybit_turnover_24h < 1_000_000:
        fail_reasons.append("Bybit合約量低於1M")
    if score < HIGH_ALERT_SCORE:
        fail_reasons.append(f"分數低於{HIGH_ALERT_SCORE}")
    if direction == "WATCH":
        fail_reasons.append("方向未確認")
    if oi_1h_pct is None and oi_4h_pct is None:
        fail_reasons.append("缺少OI確認")

    return Candidate(
        symbol=symbol,
        base_symbol=symbol.removesuffix("USDT"),
        name=cmc.get("name", ""),
        cmc_rank=cmc.get("cmc_rank"),
        market_cap=market_cap,
        market_cap_bucket=bucket,
        cmc_volume_24h=cmc_volume_24h,
        bybit_turnover_24h=bybit_turnover_24h,
        volume_to_mcap_pct=volume_to_mcap_pct,
        pct_1h=pct_1h,
        pct_24h=pct_24h,
        pct_7d=pct_7d,
        oi_1h_pct=oi_1h_pct,
        oi_4h_pct=oi_4h_pct,
        funding_rate_pct=funding_rate_pct,
        last_price=last_price,
        high_24h=high_24h,
        low_24h=low_24h,
        score=score,
        level=level_for(score, direction),
        direction=direction,
        direction_icon=icon,
        confidence=confidence,
        tags=tags[:4],
        reasons=(fail_reasons + reasons)[:5],
    )


def format_usd(value: float) -> str:
    abs_value = abs(value)
    if abs_value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if abs_value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if abs_value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:.0f}"


def build_candidate(
    symbol: str,
    bybit: dict[str, Any],
    cmc: dict[str, Any],
    oi_1h_pct: float | None = None,
    oi_4h_pct: float | None = None,
) -> Candidate | None:
    quote = cmc.get("quote", {}).get("USD", {})
    market_cap = to_float(quote.get("market_cap"))
    market_cap_points, bucket = market_cap_score(market_cap)
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
    last_price = to_float(bybit.get("lastPrice"))
    high_24h = to_float(bybit.get("highPrice24h"))
    low_24h = to_float(bybit.get("lowPrice24h"))
    volume_to_mcap_pct = (cmc_volume_24h / market_cap * 100) if market_cap else 0

    score = 10
    score += market_cap_points
    score += volume_score(volume_to_mcap_pct)
    score += momentum_score(pct_1h, pct_24h, pct_7d)
    score += oi_score(oi_1h_pct, oi_4h_pct)
    score += funding_score(funding_rate_pct)
    if bybit_turnover_24h >= 5_000_000:
        score += 5
    score += risk_penalty(pct_1h, pct_24h, pct_7d, volume_to_mcap_pct, funding_rate_pct, oi_1h_pct, oi_4h_pct)
    score = max(0, min(100, int(score)))

    direction, icon, confidence, tags, reasons = direction_for(
        market_cap,
        pct_1h,
        pct_24h,
        pct_7d,
        volume_to_mcap_pct,
        funding_rate_pct,
        oi_1h_pct,
        oi_4h_pct,
        last_price,
        high_24h,
    )

    if market_cap < 100_000_000:
        if volume_to_mcap_pct < 20 or bybit_turnover_24h < 5_000_000:
            if direction == "LONG":
                direction, icon, confidence = "WATCH-LONG", "🌱", "中"
            score = min(score, 74)
            reasons.append("低市值需更高成交量，先列早期觀察")
    elif market_cap < 300_000_000:
        if volume_to_mcap_pct < 12 or bybit_turnover_24h < 3_000_000:
            if direction == "LONG":
                direction, icon, confidence = "WATCH-LONG", "🌱", "中"
            score = min(score, 74)
            reasons.append("100M-300M 量能未達 HIGH，先列早期觀察")

    if pct_1h > 15 or pct_24h > 60 or pct_7d > 250:
        if direction == "LONG":
            direction, icon, confidence = "WATCH-LONG", "👀", "低"
            reasons.append("不追高保護")
            score = min(score, 79)

    if direction in {"LONG", "SHORT"} and oi_1h_pct is None and oi_4h_pct is None:
        direction, icon, confidence = "WATCH-LONG" if direction == "LONG" else "WATCH-SHORT", "⏳", "低"
        score = min(score, 79)
        reasons.append("缺少OI確認")

    level = level_for(score, direction)
    if level not in {"HIGH", "EARLY"}:
        return None

    return Candidate(
        symbol=symbol,
        base_symbol=symbol.removesuffix("USDT"),
        name=cmc.get("name", ""),
        cmc_rank=cmc.get("cmc_rank"),
        market_cap=market_cap,
        market_cap_bucket=bucket,
        cmc_volume_24h=cmc_volume_24h,
        bybit_turnover_24h=bybit_turnover_24h,
        volume_to_mcap_pct=volume_to_mcap_pct,
        pct_1h=pct_1h,
        pct_24h=pct_24h,
        pct_7d=pct_7d,
        oi_1h_pct=oi_1h_pct,
        oi_4h_pct=oi_4h_pct,
        funding_rate_pct=funding_rate_pct,
        last_price=last_price,
        high_24h=high_24h,
        low_24h=low_24h,
        score=score,
        level=level,
        direction=direction,
        direction_icon=icon,
        confidence=confidence,
        tags=tags[:4],
        reasons=reasons[:4],
    )


def format_candidate(candidate: Candidate) -> str:
    side_icon = "🟢" if "LONG" in candidate.direction else "🔴" if "SHORT" in candidate.direction else "🟡"
    level_icon = "🚀" if candidate.level == "HIGH" else "🌱" if candidate.level == "EARLY" else "👀"
    direction_text = display_direction(candidate.direction)
    if candidate.direction == "WATCH":
        title = f"{side_icon}{level_icon} 小幣雷達 | {candidate.level} | 待觀察"
    elif candidate.direction.startswith("WATCH"):
        title = f"{side_icon}{level_icon} 小幣雷達 | {candidate.level} | {direction_text}"
    else:
        title = f"{side_icon}{level_icon} 小幣合約機會 | {candidate.level} | {direction_text}"
    reasons = "\n".join(f"• {item}" for item in candidate.reasons) if candidate.reasons else "• 條件接近，等待確認"
    tags = "  ".join(f"#{item}" for item in candidate.tags) if candidate.tags else "#無"
    oi_1h = "N/A" if candidate.oi_1h_pct is None else f"{candidate.oi_1h_pct:+.1f}%"
    oi_4h = "N/A" if candidate.oi_4h_pct is None else f"{candidate.oi_4h_pct:+.1f}%"
    direction_reasons = "\n".join(f"• {item}" for item in direction_explanation(candidate))

    return "\n".join(
        [
            title,
            "",
            f"【{candidate.symbol}】{candidate.name or candidate.base_symbol}",
            f"分數：{score_bar(candidate.score)}",
            f"方向判斷：{direction_text}｜信心：{candidate.confidence}",
            f"標籤：{tags}",
            "",
            "🧭 方向理由",
            direction_reasons,
            "",
            "📊 價格動能",
            f"1h {candidate.pct_1h:+.1f}%｜24h {candidate.pct_24h:+.1f}%｜7d {candidate.pct_7d:+.1f}%",
            "",
            "📈 合約/量能",
            f"OI 1h {oi_1h}｜OI 4h {oi_4h}",
            f"24h量/市值 {candidate.volume_to_mcap_pct:.1f}%｜合約量 {format_usd(candidate.bybit_turnover_24h)}",
            f"資金費率 {candidate.funding_rate_pct:+.3f}%",
            "",
            "🏷 基本資料",
            f"市值 {format_usd(candidate.market_cap)}｜區間 {candidate.market_cap_bucket}｜CMC #{candidate.cmc_rank or 'N/A'}",
            "",
            "為什麼推：",
            reasons,
            "",
            "下一步：",
            next_step_text(candidate),
            "",
            "提醒：這是雷達訊號，不是直接下單建議；進場仍要看型態、止損與流動性。",
        ]
    )


def score_bar(score: int) -> str:
    filled = max(0, min(10, round(score / 10)))
    return f"{'█' * filled}{'░' * (10 - filled)} {score}/100"


def display_direction(direction: str) -> str:
    if direction == "LONG":
        return "LONG"
    if direction == "SHORT":
        return "SHORT"
    if direction == "WATCH-LONG":
        return "LONG（早期觀察）"
    if direction == "WATCH-SHORT":
        return "SHORT（早期觀察）"
    return "待觀察"


def direction_explanation(candidate: Candidate) -> list[str]:
    if candidate.direction == "LONG":
        return [
            "1h/24h 價格動能偏多",
            "24h量/市值達到啟動門檻",
            "OI 或資金費率至少有一項支持多方",
        ]
    if candidate.direction == "SHORT":
        return [
            "短線價格轉弱或過熱後回落",
            "OI 增加代表合約部位仍在堆疊",
            "偏空訊號比偏多訊號更明確",
        ]
    if candidate.direction == "WATCH-LONG":
        return [
            "價格與量能偏多，但確認條件還沒完全補齊",
            "目前先列為早期 LONG，不當成完整強訊號",
            "需要看 4H 回踩、OI 或續量確認",
        ]
    if candidate.direction == "WATCH-SHORT":
        return [
            "價格或資金費率有偏空跡象，但確認條件還沒完全補齊",
            "目前先列為早期 SHORT，不當成完整強訊號",
            "需要看 4H 反彈無力或 OI 續增確認",
        ]

    reasons = ["分數達標，但多空方向尚未乾淨"]
    if candidate.oi_1h_pct is None and candidate.oi_4h_pct is None:
        reasons.append("OI 1h/4h 皆為 N/A，缺少合約持倉確認")
    if candidate.pct_1h * candidate.pct_24h < 0:
        reasons.append("1h 與 24h 動能方向衝突")
    if candidate.pct_24h > 40 or candidate.pct_7d > 150:
        reasons.append("短期漲幅偏高，追價風險較大")
    return reasons


def next_step_text(candidate: Candidate) -> str:
    if candidate.direction == "LONG":
        return "到 TradingView 看 4H 是否回踩不破、量能是否延續，再決定進場與止損。"
    if candidate.direction == "SHORT":
        return "到 TradingView 看反彈是否站不回壓力區，避免在急跌後直接追空。"
    if candidate.direction == "WATCH-LONG":
        return "等待 4H 回踩不破、OI 補上或放量延續，才比較像可交易 LONG。"
    if candidate.direction == "WATCH-SHORT":
        return "等待 4H 反彈無力、OI 續增或資金費率偏擁擠，才比較像可交易 SHORT。"
    return "先放入待觀察；等方向、OI 或 4H 結構變乾淨再判斷。"


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def detect_u_bottom_candidate(
    symbol: str,
    cmc: dict[str, Any],
    daily_klines: list[dict[str, Any]],
    h4_klines: list[dict[str, Any]],
) -> UBottomCandidate | None:
    if len(daily_klines) < 60 or len(h4_klines) < 40:
        return None

    quote = cmc.get("quote", {}).get("USD", {})
    market_cap = to_float(quote.get("market_cap"))
    market_cap_points, bucket = market_cap_score(market_cap)
    if market_cap_points < 0:
        return None

    daily = daily_klines[-120:]
    h4 = h4_klines[-120:]
    closes = [to_float(item.get("close")) for item in daily]
    highs = [to_float(item.get("high")) for item in daily]
    lows = [to_float(item.get("low")) for item in daily]
    volumes = [to_float(item.get("volume")) for item in daily]
    if not closes or min(closes[-10:]) <= 0:
        return None

    last_price = closes[-1]
    high_90d = max(highs[-90:])
    low_90d = min(lows[-90:])
    low_30d = min(lows[-30:])
    high_30d = max(highs[-30:])
    prev_30d_high = max(highs[-31:-1])
    recent_14d_low = min(lows[-14:])
    drawdown_pct = (high_90d - low_90d) / high_90d * 100 if high_90d else 0
    bounce_from_low_pct = (last_price - low_30d) / low_30d * 100 if low_30d else 0
    distance_to_30d_high_pct = (last_price - prev_30d_high) / prev_30d_high * 100 if prev_30d_high else 0
    volume_ratio = _average(volumes[-3:]) / _average(volumes[-30:-3]) if _average(volumes[-30:-3]) else 0

    h4_closes = [to_float(item.get("close")) for item in h4]
    h4_volumes = [to_float(item.get("volume")) for item in h4]
    h4_trend_pct = (h4_closes[-1] - h4_closes[-12]) / h4_closes[-12] * 100 if h4_closes[-12] else 0
    h4_volume_ratio = _average(h4_volumes[-6:]) / _average(h4_volumes[-48:-6]) if _average(h4_volumes[-48:-6]) else 0

    score = 0
    reasons: list[str] = []
    tags: list[str] = []

    if drawdown_pct >= 50:
        score += 20
        reasons.append(f"90日高點回落 {drawdown_pct:.0f}%，有完整洗盤空間")
        tags.append("深跌後修復")
    if recent_14d_low > low_30d * 1.03:
        score += 18
        reasons.append("近14日低點抬高，右側底部開始墊高")
        tags.append("低點抬高")
    if 12 <= bounce_from_low_pct <= 120:
        score += 18
        reasons.append(f"距30日低點反彈 {bounce_from_low_pct:.0f}%，不是剛落刀也還沒過熱")
        tags.append("右側回升")
    if distance_to_30d_high_pct >= -8:
        score += 18
        reasons.append("價格接近或突破30日結構高點")
        tags.append("接近頸線")
    if volume_ratio >= 1.4:
        score += 14
        reasons.append(f"日線近3日量能約為前段 {volume_ratio:.1f} 倍")
        tags.append("日線放量")
    if h4_trend_pct >= 3 and h4_volume_ratio >= 1.1:
        score += 12
        reasons.append("4小時線同步放量上彎，右側確認較佳")
        tags.append("4H確認")

    if drawdown_pct < 45 or bounce_from_low_pct < 8 or distance_to_30d_high_pct < -15:
        return None
    if score < 70:
        return None

    return UBottomCandidate(
        symbol=symbol,
        base_symbol=symbol.removesuffix("USDT"),
        name=cmc.get("name", ""),
        cmc_rank=cmc.get("cmc_rank"),
        market_cap=market_cap,
        market_cap_bucket=bucket,
        score=max(0, min(100, int(score))),
        last_price=last_price,
        low_90d=low_90d,
        high_90d=high_90d,
        bounce_from_low_pct=bounce_from_low_pct,
        distance_to_30d_high_pct=distance_to_30d_high_pct,
        daily_volume_ratio=volume_ratio,
        h4_volume_ratio=h4_volume_ratio,
        h4_trend_pct=h4_trend_pct,
        tags=tags[:5],
        reasons=reasons[:5],
    )


def format_u_bottom_candidate(candidate: UBottomCandidate) -> str:
    tags = "  ".join(f"#{item}" for item in candidate.tags) if candidate.tags else "#U型底"
    reasons = "\n".join(f"• {item}" for item in candidate.reasons)
    return "\n".join(
        [
            f"🟣🥣 U型底反轉雷達 | DAILY主 / 4H輔 | {candidate.symbol}",
            "",
            f"【{candidate.symbol}】{candidate.name or candidate.base_symbol}",
            f"分數：{score_bar(candidate.score)}",
            f"標籤：{tags}",
            "",
            "📐 結構",
            f"90日高點 {candidate.high_90d:.6g}｜90日低點 {candidate.low_90d:.6g}｜現價 {candidate.last_price:.6g}",
            f"低點反彈 {candidate.bounce_from_low_pct:+.1f}%｜距30日頸線 {candidate.distance_to_30d_high_pct:+.1f}%",
            "",
            "📊 量能確認",
            f"日線近3日量能 {candidate.daily_volume_ratio:.1f}x｜4H量能 {candidate.h4_volume_ratio:.1f}x｜4H趨勢 {candidate.h4_trend_pct:+.1f}%",
            "",
            "為什麼推：",
            reasons,
            "",
            "提醒：U型底屬於早期結構訊號，適合再到 TradingView 看頸線、回踩與止損位置。",
        ]
    )
