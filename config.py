from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_env(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    cmc_api_key: str
    telegram_bot_token: str
    telegram_chat_id: str
    telegram_thread_id: int | None
    scan_interval_seconds: int
    dry_run: bool
    sqlite_path: str
    min_cmc_volume_usd: float
    min_bybit_turnover_usd: float
    cooldown_hours: int
    min_alert_score: int
    daily_alert_limit: int
    high_alert_score: int
    early_alert_score: int
    high_daily_limit: int
    early_daily_limit: int
    u_bottom_limit: int
    u_bottom_cooldown_days: int
    send_watch_alerts: bool


def get_settings() -> Settings:
    load_env()
    thread_id = os.getenv("TELEGRAM_THREAD_ID", "").strip()

    return Settings(
        cmc_api_key=os.getenv("CMC_API_KEY", "").strip(),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        telegram_thread_id=int(thread_id) if thread_id else None,
        scan_interval_seconds=int(os.getenv("SCAN_INTERVAL_SECONDS", "600")),
        dry_run=_bool_env("DRY_RUN", True),
        sqlite_path=os.getenv("SQLITE_PATH", "smallcap_alerts.sqlite"),
        min_cmc_volume_usd=float(os.getenv("MIN_CMC_VOLUME_USD", "500000")),
        min_bybit_turnover_usd=float(os.getenv("MIN_BYBIT_TURNOVER_USD", "1000000")),
        cooldown_hours=int(os.getenv("COOLDOWN_HOURS", "24")),
        min_alert_score=int(os.getenv("MIN_ALERT_SCORE", "85")),
        daily_alert_limit=int(os.getenv("DAILY_ALERT_LIMIT", "5")),
        high_alert_score=int(os.getenv("HIGH_ALERT_SCORE", "75")),
        early_alert_score=int(os.getenv("EARLY_ALERT_SCORE", "70")),
        high_daily_limit=int(os.getenv("HIGH_DAILY_LIMIT", "5")),
        early_daily_limit=int(os.getenv("EARLY_DAILY_LIMIT", "5")),
        u_bottom_limit=int(os.getenv("U_BOTTOM_LIMIT", "5")),
        u_bottom_cooldown_days=int(os.getenv("U_BOTTOM_COOLDOWN_DAYS", "7")),
        send_watch_alerts=_bool_env("SEND_WATCH_ALERTS", False),
    )
