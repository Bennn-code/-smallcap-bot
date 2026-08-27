# smallcap-bot

小幣合約雷達，用來掃描 USDT 永續合約裡「接近爆發或轉弱」的小幣標的，並把高分訊號或每日摘要推送到 Telegram 群組 topic。

> 這是訊號觀察工具，不是自動下單程式，也不是投資建議。

## 功能

- 掃描 USDT 永續合約市場
- 用 CoinMarketCap 補市值、排名、成交量、1h/24h/7d 漲跌幅
- 用合約成交量、資金費率、OI 變化做分數判斷
- 只推送高分且方向明確的 LONG / SHORT
- 用 SQLite 記錄推送紀錄，避免同一顆幣短時間洗版
- 支援 Telegram topic 推送
- 支援 Oracle VM + cron 長期自動執行

## 資料源順序

程式會依序嘗試合約交易所資料源：

1. Bybit
2. BingX
3. Binance

如果 Oracle 或雲端 IP 被某個交易所擋掉，程式會自動往下一個資料源嘗試。

CoinMarketCap 仍然負責市值和排名資料。

## 檔案用途

```text
clients.py      API 連線：交易所、CoinMarketCap、Telegram
config.py       讀取 .env 設定
scanner.py      掃描流程、Telegram 推送、CLI 入口
scoring.py      分數、方向、訊息格式
storage.py      SQLite 紀錄，避免重複推送
.env.example    設定範本，複製成 .env 後填入自己的 key
.gitignore      避免把 key、SQLite、快取檔上傳到 GitHub
```

## 設定

複製 `.env.example` 成 `.env`，再填入自己的資料：

```env
CMC_API_KEY=your_coinmarketcap_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
TELEGRAM_THREAD_ID=
SCAN_INTERVAL_SECONDS=600
DRY_RUN=true
MIN_ALERT_SCORE=85
DAILY_ALERT_LIMIT=5
COOLDOWN_HOURS=24
SEND_WATCH_ALERTS=false
```

正式推送 Telegram 時，改成：

```env
DRY_RUN=false
```

重要：不要把 `.env` 上傳到 GitHub。裡面有 API key 和 Telegram bot token。

## 執行

單次正式掃描：

```bash
python scanner.py --once
```

診斷模式：

```bash
python scanner.py --once --debug --max-alerts 5
```

每日摘要：

```bash
python scanner.py --once --summary --max-alerts 5
```

長期執行：

```bash
python scanner.py
```

## Oracle VM Cron

Oracle VM 上建議用 cron 固定執行：

```cron
*/10 * * * * cd /home/ubuntu/smallcap-bot && /home/ubuntu/smallcap-bot/.venv/bin/python scanner.py --once >> /home/ubuntu/smallcap-bot/cron.log 2>&1
0 1 * * * cd /home/ubuntu/smallcap-bot && /home/ubuntu/smallcap-bot/.venv/bin/python scanner.py --once --summary --max-alerts 5 >> /home/ubuntu/smallcap-bot/cron.log 2>&1
```

第二行的 `0 1 * * *` 是 UTC 01:00，也就是台灣時間早上 9 點。

查看 cron log：

```bash
tail -n 50 ~/smallcap-bot/cron.log
```

## 評分邏輯

偏好的標的特徵：

- 市值主要偏好 `300M - 1B`，其次 `1B - 3B`
- 成交量相對市值放大
- OI 1h / 4h 增加
- 資金費率健康
- 價格有啟動但避免過度追高

預設只有符合以下條件才推送：

```text
分數 >= 85
方向 = LONG 或 SHORT
未超過每日推送上限
未在 cooldown 時間內重複推送
```

## 安全提醒

- `.env` 不要上傳
- `smallcap_alerts.sqlite` 不要上傳
- SSH private key 不要上傳
- 曾經貼到聊天中的 API key 建議重新產生
