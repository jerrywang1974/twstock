# -*- coding: utf-8 -*-
"""Fetch daily institutional investor buy/sell (三大法人) for the full market.

Sources:
- TWSE T86 (listed)
- TPEx daily institutional trade (OTC)

Units from the exchanges are shares (股). Use ``to_lots`` for 張.
``broker_detail`` is reserved for a later broker/branch-level phase.
"""

from __future__ import annotations

import datetime
from collections import namedtuple
from typing import Iterable, List, Optional, Sequence, Union

from twstock.proxy import get_proxies, get_session

try:
    from json.decoder import JSONDecodeError
except ImportError:  # pragma: no cover
    JSONDecodeError = ValueError


Institutional = namedtuple(
    "Institutional",
    [
        "date",
        "market",
        "code",
        "name",
        "foreign_buy",
        "foreign_sell",
        "foreign_net",
        "foreign_dealer_buy",
        "foreign_dealer_sell",
        "foreign_dealer_net",
        "trust_buy",
        "trust_sell",
        "trust_net",
        "dealer_self_buy",
        "dealer_self_sell",
        "dealer_self_net",
        "dealer_hedge_buy",
        "dealer_hedge_sell",
        "dealer_hedge_net",
        "dealer_net",
        "total_net",
        "broker_detail",
    ],
)


class InstitutionalFetchError(RuntimeError):
    """Raised when an institutional feed cannot be parsed or is unavailable."""


def _to_int(value) -> int:
    if value is None:
        return 0
    text = str(value).strip().replace(",", "").replace("--", "")
    if text in ("", "null", "None", "NaN"):
        return 0
    return int(float(text))


def _as_date(value: Union[str, datetime.date, datetime.datetime]) -> datetime.date:
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    text = str(value).strip()
    if "/" in text and len(text.split("/")[0]) <= 3:
        parts = text.replace("*", "").replace("＊", "").split("/")
        year = int(parts[0]) + 1911
        return datetime.date(year, int(parts[1]), int(parts[2]))
    if "-" in text:
        return datetime.datetime.strptime(text[:10], "%Y-%m-%d").date()
    if len(text) == 8 and text.isdigit():
        return datetime.datetime.strptime(text, "%Y%m%d").date()
    raise ValueError(f"Unsupported date format: {value!r}")


def _ymd(d: datetime.date) -> str:
    return d.strftime("%Y%m%d")


def _roc(d: datetime.date) -> str:
    return f"{d.year - 1911}/{d.month:02d}/{d.day:02d}"


class BaseInstitutionalFetcher:
    market: str = ""

    def fetch(
        self, date: Union[str, datetime.date, datetime.datetime], retry: int = 5
    ) -> List[Institutional]:
        raise NotImplementedError

    def _session_get_json(self, url: str, params: dict, retry: int = 5):
        session = get_session()
        last_error: Optional[Exception] = None
        for _ in range(retry):
            try:
                response = session.get(
                    url, params=params, proxies=get_proxies(), timeout=60
                )
                return response.json()
            except (JSONDecodeError, ValueError, OSError) as exc:
                last_error = exc
                continue
        raise InstitutionalFetchError(f"Failed to fetch {url}: {last_error}")


class TWSEInstitutionalFetcher(BaseInstitutionalFetcher):
    """TWSE T86 — full-market listed institutional day report."""

    market = "twse"
    REPORT_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"

    def fetch(
        self, date: Union[str, datetime.date, datetime.datetime], retry: int = 5
    ) -> List[Institutional]:
        day = _as_date(date)
        payload = self._session_get_json(
            self.REPORT_URL,
            {
                "date": _ymd(day),
                "selectType": "ALLBUT0999",
                "response": "json",
            },
            retry=retry,
        )
        if payload.get("stat") != "OK":
            return []
        rows = payload.get("data") or []
        return [self._make_row(day, row) for row in rows if row]

    def _make_row(self, day: datetime.date, row: Sequence) -> Institutional:
        return Institutional(
            date=day,
            market=self.market,
            code=str(row[0]).strip(),
            name=str(row[1]).strip(),
            foreign_buy=_to_int(row[2]),
            foreign_sell=_to_int(row[3]),
            foreign_net=_to_int(row[4]),
            foreign_dealer_buy=_to_int(row[5]),
            foreign_dealer_sell=_to_int(row[6]),
            foreign_dealer_net=_to_int(row[7]),
            trust_buy=_to_int(row[8]),
            trust_sell=_to_int(row[9]),
            trust_net=_to_int(row[10]),
            dealer_net=_to_int(row[11]),
            dealer_self_buy=_to_int(row[12]),
            dealer_self_sell=_to_int(row[13]),
            dealer_self_net=_to_int(row[14]),
            dealer_hedge_buy=_to_int(row[15]),
            dealer_hedge_sell=_to_int(row[16]),
            dealer_hedge_net=_to_int(row[17]),
            total_net=_to_int(row[18]),
            broker_detail=None,
        )


class TPEXInstitutionalFetcher(BaseInstitutionalFetcher):
    """TPEx OTC institutional day report (外資/投信/自營商)."""

    market = "tpex"
    REPORT_URL = "https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade"
    FALLBACK_URL = (
        "https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php"
    )

    def fetch(
        self, date: Union[str, datetime.date, datetime.datetime], retry: int = 5
    ) -> List[Institutional]:
        day = _as_date(date)
        payload = self._fetch_payload(day, retry=retry)
        tables = payload.get("tables") or []
        if not tables:
            return []
        rows = tables[0].get("data") or []
        return [self._make_row(day, row) for row in rows if row]

    def _fetch_payload(self, day: datetime.date, retry: int = 5) -> dict:
        params_primary = {
            "date": f"{day.year}/{day.month:02d}/{day.day:02d}",
            "type": "Daily",
            "cate": "ALL",
            "search": "",
            "response": "json",
        }
        try:
            payload = self._session_get_json(
                self.REPORT_URL, params_primary, retry=retry
            )
            if payload.get("tables"):
                return payload
        except InstitutionalFetchError:
            pass

        params_fallback = {"d": _roc(day), "o": "json"}
        return self._session_get_json(
            self.FALLBACK_URL, params_fallback, retry=retry
        )

    def _make_row(self, day: datetime.date, row: Sequence) -> Institutional:
        # Groups after code/name (each buy/sell/net):
        # foreign excl dealer, foreign dealer, foreign total,
        # trust, dealer self, dealer hedge, dealer total, then total_net.
        foreign_buy = _to_int(row[2])
        foreign_sell = _to_int(row[3])
        foreign_net = _to_int(row[4])
        foreign_dealer_buy = _to_int(row[5])
        foreign_dealer_sell = _to_int(row[6])
        foreign_dealer_net = _to_int(row[7])
        trust_buy = _to_int(row[11])
        trust_sell = _to_int(row[12])
        trust_net = _to_int(row[13])
        dealer_self_buy = _to_int(row[14])
        dealer_self_sell = _to_int(row[15])
        dealer_self_net = _to_int(row[16])
        dealer_hedge_buy = _to_int(row[17])
        dealer_hedge_sell = _to_int(row[18])
        dealer_hedge_net = _to_int(row[19])
        dealer_net = (
            _to_int(row[22])
            if len(row) > 22
            else dealer_self_net + dealer_hedge_net
        )
        total_net = (
            _to_int(row[23])
            if len(row) > 23
            else foreign_net + foreign_dealer_net + trust_net + dealer_net
        )
        return Institutional(
            date=day,
            market=self.market,
            code=str(row[0]).strip(),
            name=str(row[1]).strip(),
            foreign_buy=foreign_buy,
            foreign_sell=foreign_sell,
            foreign_net=foreign_net,
            foreign_dealer_buy=foreign_dealer_buy,
            foreign_dealer_sell=foreign_dealer_sell,
            foreign_dealer_net=foreign_dealer_net,
            trust_buy=trust_buy,
            trust_sell=trust_sell,
            trust_net=trust_net,
            dealer_self_buy=dealer_self_buy,
            dealer_self_sell=dealer_self_sell,
            dealer_self_net=dealer_self_net,
            dealer_hedge_buy=dealer_hedge_buy,
            dealer_hedge_sell=dealer_hedge_sell,
            dealer_hedge_net=dealer_hedge_net,
            dealer_net=dealer_net,
            total_net=total_net,
            broker_detail=None,
        )


def fetch(
    date: Union[str, datetime.date, datetime.datetime],
    markets: Optional[Iterable[str]] = None,
    retry: int = 5,
) -> List[Institutional]:
    """Fetch full-market institutional data for a trade date.

    Args:
        date: trade date (YYYYMMDD / YYYY-MM-DD / date / datetime)
        markets: iterable of ``twse`` and/or ``tpex`` (default both)
        retry: HTTP retry count per market
    """
    selected = [m.lower() for m in (markets or ("twse", "tpex"))]
    fetchers = {
        "twse": TWSEInstitutionalFetcher(),
        "tpex": TPEXInstitutionalFetcher(),
    }
    results: List[Institutional] = []
    for market in selected:
        if market not in fetchers:
            raise ValueError(f"Unknown market: {market}")
        results.extend(fetchers[market].fetch(date, retry=retry))
    return results


def to_lots(value_shares: int) -> float:
    """Convert shares (股) to lots (張)."""
    return value_shares / 1000.0


def top_by(
    rows: Sequence[Institutional],
    field: str = "trust_net",
    limit: int = 20,
    descending: bool = True,
) -> List[Institutional]:
    """Return top rows sorted by an Institutional field (e.g. trust_net)."""
    return sorted(rows, key=lambda r: getattr(r, field), reverse=descending)[:limit]
