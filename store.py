"""SQLite 快取：保存每日持股，供差異比對與下拉選單使用。

只是加速用的快取 —— 重部署/休眠清空也沒關係，ezmoney 有完整歷史可重抓。
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import date

DB_PATH = os.environ.get(
    "DB_PATH", os.path.join(os.path.dirname(__file__), "data", "portfolio.db")
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS holdings (
    stock_no    TEXT NOT NULL,
    tran_date   TEXT NOT NULL,   -- ISO 西元日期 YYYY-MM-DD
    detail_code TEXT NOT NULL,
    detail_name TEXT NOT NULL,
    share       INTEGER NOT NULL,
    weight      REAL NOT NULL,
    amount      REAL NOT NULL,
    PRIMARY KEY (stock_no, tran_date, detail_code)
);
"""


def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _connect() as conn:
        conn.executescript(_SCHEMA)


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def save_portfolio(stock_no: str, tran_date: date, holdings: list[dict]) -> None:
    """寫入（UPSERT）某 ETF 某日的全部持股。"""
    if not holdings:
        return
    iso = tran_date.isoformat()
    rows = [
        (stock_no, iso, h["code"], h["name"], h["share"], h["weight"], h["amount"])
        for h in holdings
    ]
    with _connect() as conn:
        conn.executemany(
            """
            INSERT INTO holdings
                (stock_no, tran_date, detail_code, detail_name, share, weight, amount)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(stock_no, tran_date, detail_code) DO UPDATE SET
                detail_name = excluded.detail_name,
                share       = excluded.share,
                weight      = excluded.weight,
                amount      = excluded.amount
            """,
            rows,
        )


def get_portfolio(stock_no: str, tran_date: date) -> list[dict]:
    """讀取某 ETF 某日持股（依權重由大到小）；查無回傳空 list。"""
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT detail_code AS code, detail_name AS name,
                   share, weight, amount
            FROM holdings
            WHERE stock_no = ? AND tran_date = ?
            ORDER BY weight DESC
            """,
            (stock_no, tran_date.isoformat()),
        )
        return [dict(r) for r in cur.fetchall()]


def list_dates(stock_no: str) -> list[str]:
    """回傳某 ETF 已存的所有日期（ISO 字串，新到舊）。"""
    with _connect() as conn:
        cur = conn.execute(
            "SELECT DISTINCT tran_date FROM holdings WHERE stock_no = ? "
            "ORDER BY tran_date DESC",
            (stock_no,),
        )
        return [r["tran_date"] for r in cur.fetchall()]
