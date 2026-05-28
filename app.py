"""Flask 後端：代理 ezmoney GetPCF、快取、提供 API 與單頁前端。"""
from __future__ import annotations

import os
from datetime import date

from flask import Flask, jsonify, request, send_from_directory

import store
from ezmoney import FUND_CODES, EzmoneyError, fetch_pcf
from holidays import default_query_date

app = Flask(__name__, static_folder="static", static_url_path="")
store.init_db()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


def _parse_iso(s: str) -> date:
    y, m, d = (int(p) for p in s.split("-"))
    return date(y, m, d)


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/api/etfs")
def api_etfs():
    """可選的 ETF 清單。"""
    return jsonify(list(FUND_CODES.keys()))


@app.route("/api/default_date")
def api_default_date():
    """依台北時間回傳預設查詢日期（16:30 後為當天，否則為前一交易日）。"""
    return jsonify({"date": default_query_date().isoformat()})


@app.route("/api/portfolio")
def api_portfolio():
    """取得某 ETF 某日投資組合。date 省略＝抓最新一日。

    先查快取；查無則連線 ezmoney 抓取並寫入快取。
    """
    etf = request.args.get("etf", "")
    if etf not in FUND_CODES:
        return jsonify({"error": "未知的 ETF 代號"}), 400

    date_str = request.args.get("date")
    if date_str:
        want_date = _parse_iso(date_str)
    else:
        # 沒帶日期：依台北時間決定預設 — 16:30 後當日 PCF 已揭露用當天，否則用前一交易日
        want_date = default_query_date()

    # 有指定日且快取已有 -> 直接回快取
    if want_date:
        cached = store.get_portfolio(etf, want_date)
        if cached:
            return jsonify(
                {
                    "etf": etf,
                    "tran_date": want_date.isoformat(),
                    "holdings": cached,
                    "cached": True,
                }
            )

    # 否則連線抓取
    try:
        result = fetch_pcf(etf, want_date)
    except EzmoneyError as e:
        return jsonify({"error": str(e)}), 502

    tran_date = result["tran_date"]
    if not result["holdings"] or tran_date is None:
        # 回傳實際請求的日期 (避免預設日 ezmoney 尚未有資料時 UI 變空)
        fallback_iso = date_str or want_date.isoformat()
        return jsonify(
            {
                "etf": etf,
                "tran_date": fallback_iso,
                "holdings": [],
                "message": "當日無資料（可能為非揭露日或基金成立前）",
            }
        )

    store.save_portfolio(etf, tran_date, result["holdings"])
    return jsonify(
        {
            "etf": etf,
            "fund_name": result["fund_name"],
            "tran_date": tran_date.isoformat(),
            "holdings": result["holdings"],
            "cached": False,
        }
    )


@app.route("/api/dates")
def api_dates():
    """某 ETF 已快取的日期清單（給比較基準日下拉用）。"""
    etf = request.args.get("etf", "")
    if etf not in FUND_CODES:
        return jsonify({"error": "未知的 ETF 代號"}), 400
    return jsonify(store.list_dates(etf))


def _ensure_portfolio(etf: str, d: date) -> list[dict]:
    """取得某日持股：先查快取，無則抓取並存。"""
    cached = store.get_portfolio(etf, d)
    if cached:
        return cached
    result = fetch_pcf(etf, d)
    if result["holdings"] and result["tran_date"]:
        store.save_portfolio(etf, result["tran_date"], result["holdings"])
        # 抓回來的真正資料日可能與請求日不同
        if result["tran_date"] == d:
            return result["holdings"]
        return store.get_portfolio(etf, result["tran_date"]) or result["holdings"]
    return []


@app.route("/api/diff")
def api_diff():
    """比對 date 與 base 兩日的投資組合差異。

    回傳三類：added(新增) / removed(移除) / changed(變動)。
    """
    etf = request.args.get("etf", "")
    if etf not in FUND_CODES:
        return jsonify({"error": "未知的 ETF 代號"}), 400
    try:
        cur_date = _parse_iso(request.args["date"])
        base_date = _parse_iso(request.args["base"])
    except (KeyError, ValueError):
        return jsonify({"error": "需提供 date 與 base（YYYY-MM-DD）"}), 400

    try:
        cur = {h["code"]: h for h in _ensure_portfolio(etf, cur_date)}
        base = {h["code"]: h for h in _ensure_portfolio(etf, base_date)}
    except EzmoneyError as e:
        return jsonify({"error": str(e)}), 502

    added, removed, changed = [], [], []
    for code, h in cur.items():
        if code not in base:
            added.append(h)
        else:
            b = base[code]
            if h["share"] != b["share"] or abs(h["weight"] - b["weight"]) > 1e-9:
                changed.append(
                    {
                        "code": code,
                        "name": h["name"],
                        "share": h["share"],
                        "share_prev": b["share"],
                        "share_delta": h["share"] - b["share"],
                        "weight": h["weight"],
                        "weight_prev": b["weight"],
                        "weight_delta": round(h["weight"] - b["weight"], 4),
                    }
                )
    for code, b in base.items():
        if code not in cur:
            removed.append(b)

    added.sort(key=lambda h: h["weight"], reverse=True)
    removed.sort(key=lambda h: h["weight"], reverse=True)
    changed.sort(key=lambda h: abs(h["weight_delta"]), reverse=True)

    return jsonify(
        {
            "etf": etf,
            "date": cur_date.isoformat(),
            "base": base_date.isoformat(),
            "added": added,
            "removed": removed,
            "changed": changed,
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
