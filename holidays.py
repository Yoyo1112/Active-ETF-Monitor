"""台股休市日 / 下個交易日工具。資料來源：TWSE 2026 休市日期表。
每年年底需手動更新清單。"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

TAIPEI_TZ = ZoneInfo("Asia/Taipei")
PUBLISH_CUTOFF = time(17, 30)  # 過此時間後預設下個交易日

# 2026 台股休市日 (依 TWSE 公告，平日休市才需列入；週末不必列)
# ⚠️ 最終請以 TWSE「停止交易日期表」官方檔為準再核對一次
TW_HOLIDAYS_2026: frozenset[date] = frozenset({
    date(2026, 1, 1),    # 元旦
    date(2026, 2, 16),   # 春節
    date(2026, 2, 17),
    date(2026, 2, 18),
    date(2026, 2, 19),
    date(2026, 2, 20),
    date(2026, 2, 27),   # 228 連假補假
    date(2026, 4, 3),    # 清明 / 兒童節
    date(2026, 5, 1),    # 勞動節
    date(2026, 6, 19),   # 端午
    date(2026, 9, 25),   # 中秋
    date(2026, 10, 9),   # 國慶連假
})


def is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d not in TW_HOLIDAYS_2026


def next_trading_day(d: date) -> date:
    """回傳嚴格大於 d 的下一個交易日。"""
    nxt = d + timedelta(days=1)
    while not is_trading_day(nxt):
        nxt += timedelta(days=1)
    return nxt


def default_query_date(now: datetime | None = None) -> date:
    """預設要查的 PCF 日期。

    規則：依台北時間判斷
      - 當下 ≥ 17:30 → 回傳下一個交易日 (跳過週末 + 假日)
      - 否則         → 回傳今天
    """
    if now is None:
        now = datetime.now(TAIPEI_TZ)
    if now.time() >= PUBLISH_CUTOFF:
        return next_trading_day(now.date())
    return now.date()
