"""台股休市日 / 下個交易日工具。資料來源：TWSE 2026 休市日期表。
每年年底需手動更新清單。"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

TAIPEI_TZ = ZoneInfo("Asia/Taipei")
PUBLISH_CUTOFF = time(16, 30)  # 過此時間後當日 PCF 已揭露，預設用當天

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


def previous_trading_day(d: date) -> date:
    """回傳嚴格小於 d 的前一個交易日。"""
    prev = d - timedelta(days=1)
    while not is_trading_day(prev):
        prev -= timedelta(days=1)
    return prev


def default_query_date(now: datetime | None = None) -> date:
    """預設要查的 PCF 日期。

    規則：依台北時間判斷
      - 今天是交易日且當下 ≥ 16:30 → 回傳今天 (當日 PCF 已揭露)
      - 否則                        → 回傳前一個交易日 (跳過週末 + 假日)
    """
    if now is None:
        now = datetime.now(TAIPEI_TZ)
    today = now.date()
    if is_trading_day(today) and now.time() >= PUBLISH_CUTOFF:
        return today
    return previous_trading_day(today)
