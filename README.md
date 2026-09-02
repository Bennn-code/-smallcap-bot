# smallcap-bot

這是第一版小幣合約雷達：

- 交易所公開 API：依序嘗試 Bybit、BingX、Binance，抓 USDT 永續合約、成交額、資金費率、24h 價格資料
- CoinMarketCap API：補市值、排名、1h/24h/7d 漲跌、現貨成交量
- Telegram Bot API：發到指定群組 topic
- SQLite：避免同一顆幣短時間重複洗版

## 設定

複製 `.env.example` 成 `.env`，再填入你的資料：

```env
CMC_API_KEY=你的_coinmarketcap_api_key
TELEGRAM_BOT_TOKEN=你的_telegram_bot_token
TELEGRAM_CHAT_ID=-1004323612003
TELEGRAM_THREAD_ID=4
SCAN_INTERVAL_SECONDS=600
DRY_RUN=true
MIN_ALERT_SCORE=85
DAILY_ALERT_LIMIT=5
HIGH_ALERT_SCORE=75
EARLY_ALERT_SCORE=70
HIGH_DAILY_LIMIT=0
EARLY_DAILY_LIMIT=5
COOLDOWN_HOURS=24
U_BOTTOM_LIMIT=5
U_BOTTOM_COOLDOWN_DAYS=7
SEND_WATCH_ALERTS=false
```

先用 `DRY_RUN=true` 測試，確認掃描結果合理後，再改成：

```env
DRY_RUN=false
```

## 執行

```bash
python scanner.py --once
```

測試診斷模式：

```bash
python scanner.py --once --debug --max-alerts 10
```

每日摘要模式：

```bash
python scanner.py --once --summary --max-alerts 5
```

4 小時觀察摘要模式：

```bash
python scanner.py --once --watch-summary --max-alerts 5
```

`--watch-summary` 每次執行都會發送 Telegram，不會被「一天只發一次摘要」限制擋住。它不是正式推薦，而是用來觀察最接近條件的標的，並確認 cron、API、Telegram 都有正常觸發。

U 型底反轉掃描：

```bash
python scanner.py --once --u-bottom --max-alerts 5
```

`--u-bottom` 以日線為主、4 小時線為輔。有候選會列出標的，沒有候選也會推送「本次沒有符合條件」。

長期執行：

```bash
python scanner.py
```

## Cron 建議

正式推薦維持每 10 分鐘掃描：

```cron
*/10 * * * * cd /home/ubuntu/smallcap-bot && /home/ubuntu/smallcap-bot/.venv/bin/python scanner.py --once >> /home/ubuntu/smallcap-bot/cron.log 2>&1
```

觀察摘要每 4 小時推一次：

```cron
0 */4 * * * cd /home/ubuntu/smallcap-bot && /home/ubuntu/smallcap-bot/.venv/bin/python scanner.py --once --watch-summary --max-alerts 8 >> /home/ubuntu/smallcap-bot/cron.log 2>&1
```

U 型底每三天掃一次，台灣時間約 09:30：

```cron
30 1 */3 * * cd /home/ubuntu/smallcap-bot && /home/ubuntu/smallcap-bot/.venv/bin/python scanner.py --once --u-bottom --max-alerts 5 >> /home/ubuntu/smallcap-bot/cron.log 2>&1
```

## 目前評分重點

- 市值最偏好 `300M - 1B`，其次 `1B - 3B`
- `10M - 100M` 會降分，且必須有更強成交量才可能 HIGH
- 用 `24h量/市值` 衡量放量程度
- 用 Bybit OI 1h / 4h 變化確認是否有合約持倉異動
- LONG：OI 放大、資金健康、價格溫和啟動
- SHORT：過熱後轉弱、OI 增加、資金費率偏高、短線回落
- WATCH：分數夠但方向不乾淨，預設不推送 Telegram
- HIGH：`75` 分以上，正式推薦，不受每日 `5` 則限制
- EARLY：`70-74` 分，即時推送，每天最多 `5` 則
- WATCH：`60-69` 分，只放入 4 小時觀察摘要
- 同幣同方向同等級冷卻 `24` 小時
- 同幣同方向從 EARLY 升 HIGH 可以再推一次
- 70-74 分即使方向仍是純 WATCH，也會即時推送，但 Telegram 會標成「待觀察」
- U 型底反轉用日線看底部結構，4 小時線確認右側放量與趨勢

Telegram 標題例子：

```text
🟢🚀 小幣合約機會 | HIGH | LONG
🟡🌱 小幣雷達 | EARLY | 待觀察
🔴🚀 小幣合約機會 | HIGH | SHORT
🟣🥣 U型底反轉雷達 | DAILY主 / 4H輔 | PROMUSDT
```

正式上線前，建議重新產生新的 CMC API key，並刪除曾經貼在聊天中的舊 key。
