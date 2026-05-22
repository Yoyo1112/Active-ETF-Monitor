"""ezmoney PCF (申購買回清單) 抓取與解析。

對應官網: https://www.ezmoney.com.tw/ETF/Transaction/PCF
API:       POST /ETF/Transaction/GetPCF
"""
from __future__ import annotations

import re
import time
from datetime import date, datetime

import requests

BASE = "https://www.ezmoney.com.tw"
PCF_PAGE = f"{BASE}/ETF/Transaction/PCF"
GET_PCF = f"{BASE}/ETF/Transaction/GetPCF"

# 股票代號 -> ezmoney 內部 fundCode
FUND_CODES = {
    "00981A": "49YTW",
    "00403A": "63YTW",
}

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# 模組層級共用 session，重用 cookie 以加速後續請求
_session: requests.Session | None = None

# TLS 驗證：預設開啟。少數環境（如極新的 OpenSSL）會因該站憑證缺少
# Subject Key Identifier 而驗證失敗，此時自動降級為不驗證並重試。
# 此站為公開唯讀資料，降級僅影響傳輸層驗證，不涉及任何機密。
_verify = True


class EzmoneyError(Exception):
    """抓取或解析失敗。"""


def _get_session() -> requests.Session:
    """取得（必要時建立）帶有 PCF 頁 cookie 的 session。"""
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update({"User-Agent": _UA})
        # 先 GET 一次頁面取得 ASP.NET session cookie
        s.get(PCF_PAGE, timeout=15, verify=_verify)
        _session = s
    return _session


def _handle_ssl_fallback(err: Exception) -> bool:
    """遇到 SSL 驗證錯誤時，降級為不驗證並回報是否需重試。"""
    global _verify, _session
    if isinstance(err, requests.exceptions.SSLError) and _verify:
        import urllib3

        urllib3.disable_warnings()
        _verify = False
        _session = None
        return True
    return False


def roc_to_ad(roc: str) -> date:
    """民國日期字串 (yyy/MM/dd) -> 西元 date。"""
    y, m, d = (int(p) for p in roc.strip().split("/"))
    return date(y + 1911, m, d)


def ad_to_roc(d: date) -> str:
    """西元 date -> 民國日期字串 (yyy/MM/dd)。"""
    return f"{d.year - 1911:03d}/{d.month:02d}/{d.day:02d}"


def parse_api_date(s: str) -> date | None:
    """解析 API 回傳的日期，支援兩種格式：
    - .NET：/Date(1779379200000)/
    - ISO ：2026-05-22T00:00:00
    """
    if not s:
        return None
    m = re.search(r"/Date\((\d+)\)/", s)
    if m:
        return datetime.utcfromtimestamp(int(m.group(1)) / 1000).date()
    try:
        return datetime.fromisoformat(s).date()
    except ValueError:
        return None


def _parse_holdings(data: dict) -> tuple[list[dict], date | None]:
    """從 GetPCF 回應取出股票持股清單與資料日。"""
    holdings: list[dict] = []
    tran_date: date | None = None
    for asset in data.get("asset") or []:
        if asset.get("AssetCode") != "ST":
            continue
        for d in asset.get("Details") or []:
            if tran_date is None:
                tran_date = parse_api_date(d.get("TranDate", ""))
            holdings.append(
                {
                    "code": (d.get("DetailCode") or "").strip(),
                    "name": (d.get("DetailName") or "").strip(),
                    "share": int(d.get("Share") or 0),
                    "weight": float(d.get("NavRate") or 0.0),
                    "amount": float(d.get("Amount") or 0.0),
                }
            )
    # 依權重由大到小排序
    holdings.sort(key=lambda h: h["weight"], reverse=True)
    return holdings, tran_date


def fetch_pcf(stock_no: str, ad_date: date | None = None) -> dict:
    """抓取指定 ETF 的投資組合。

    Args:
        stock_no: 股票代號，如 "00981A"。
        ad_date:  西元日期；None 表示抓最新一日。

    Returns:
        {"stock_no", "fund_name", "tran_date" (date|None),
         "holdings": [{code,name,share,weight,amount}, ...]}
    """
    if stock_no not in FUND_CODES:
        raise EzmoneyError(f"不支援的 ETF 代號: {stock_no}")

    payload = {
        "fundCode": FUND_CODES[stock_no],
        "date": ad_to_roc(ad_date) if ad_date else ad_to_roc(date.today()),
        "specificDate": ad_date is not None,
    }
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": PCF_PAGE,
    }

    last_err: Exception | None = None
    for attempt in range(3):  # 失敗重試（含一次 SSL 降級）
        try:
            s = _get_session()
            resp = s.post(GET_PCF, json=payload, headers=headers, timeout=15, verify=_verify)
            resp.raise_for_status()
            data = resp.json()
            holdings, tran_date = _parse_holdings(data)
            fund = data.get("fund") or {}
            return {
                "stock_no": stock_no,
                "fund_name": (fund.get("sFundName") or "").strip(),
                "tran_date": tran_date,
                "holdings": holdings,
            }
        except Exception as e:  # noqa: BLE001 - 統一轉成 EzmoneyError
            last_err = e
            if _handle_ssl_fallback(e):
                continue  # 立即以不驗證重試
            # 重試前重建 session（cookie 可能失效）
            global _session
            _session = None
            time.sleep(0.5)

    raise EzmoneyError(f"抓取 {stock_no} 失敗: {last_err}")
