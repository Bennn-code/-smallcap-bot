from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
    if score >= 85 and direction in {"LONG", "SHORT"}:
        return "HIGH"
    if score >= 65:
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
    if score < 85:
        fail_reasons.append("分數低於85")
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
            score = min(score, 74)
            reasons.append("低市值需更高成交量，暫列觀察")
    elif market_cap < 300_000_000:
        if volume_to_mcap_pct < 12 or bybit_turnover_24h < 3_000_000:
            score = min(score, 74)
            reasons.append("100M-300M 量能未達 HIGH 補償條件")

    if pct_1h > 15 or pct_24h > 60 or pct_7d > 250:
        if direction == "LONG":
            direction, icon, confidence = "WATCH", "👀", "低"
            reasons.append("不追高保護")
            score = min(score, 79)

    if direction in {"LONG", "SHORT"} and oi_1h_pct is None and oi_4h_pct is None:
        direction, icon, confidence = "WATCH", "⏳", "低"
        score = min(score, 79)
        reasons.append("缺少OI確認")

    level = level_for(score, direction)
    if level != "HIGH":
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
    side_icon = "🟢" if candidate.direction == "LONG" else "🔴" if candidate.direction == "SHORT" else "🟡"
    if candidate.direction == "WATCH":
        title = f"{side_icon}{candidate.direction_icon} 小幣觀察 | {candidate.level}"
    else:
        title = f"{side_icon}{candidate.direction_icon} 小幣合約機會 | {candidate.level} | {candidate.direction}"
    reasons = "、".join(candidate.reasons) if candidate.reasons else "條件接近，等待確認"
    tags = "・".join(candidate.tags) if candidate.tags else "無"
    oi_1h = "N/A" if candidate.oi_1h_pct is None else f"{candidate.oi_1h_pct:+.1f}%"
    oi_4h = "N/A" if candidate.oi_4h_pct is None else f"{candidate.oi_4h_pct:+.1f}%"

    return "\n".join(
        [
            title,
            "",
            f"幣種：{candidate.symbol}",
            f"市值區間：{candidate.market_cap_bucket}",
            f"市值：{format_usd(candidate.market_cap)}",
            f"CMC排名：{candidate.cmc_rank or 'N/A'}",
            f"分數：{candidate.score}",
            f"方向信心：{candidate.confidence}",
            f"標籤：{tags}",
            "",
            f"1h：{candidate.pct_1h:+.1f}%",
            f"24h：{candidate.pct_24h:+.1f}%",
            f"7d：{candidate.pct_7d:+.1f}%",
            f"OI 1h：{oi_1h}",
            f"OI 4h：{oi_4h}",
            f"24h量/市值：{candidate.volume_to_mcap_pct:.1f}%",
            f"合約量：{format_usd(candidate.bybit_turnover_24h)}",
            f"資金費率：{candidate.funding_rate_pct:+.3f}%",
            "",
            "原因：",
            reasons,
        ]
    )
