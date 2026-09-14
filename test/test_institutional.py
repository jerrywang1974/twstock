import datetime
import unittest
from unittest import mock

from twstock import institutional


TWSE_SAMPLE_ROW = [
    "2330",
    "台積電",
    "7,292,499",
    "15,543,629",
    "-8,251,130",
    "0",
    "0",
    "0",
    "137,349",
    "318,203",
    "-180,854",
    "-400,461",
    "97,300",
    "642,000",
    "-544,700",
    "494,409",
    "350,170",
    "144,239",
    "-8,832,445",
]

TPEX_SAMPLE_ROW = [
    "6223",
    "旺矽",
    "944,000",
    "617,000",
    "327,000",
    "0",
    "0",
    "0",
    "944,000",
    "617,000",
    "327,000",
    "56,000",
    "5,000",
    "51,000",
    "35,026",
    "15,000",
    "20,026",
    "94,722",
    "28,684",
    "66,038",
    "129,748",
    "43,684",
    "86,064",
    "464,064",
]


class HelperTest(unittest.TestCase):
    def test_to_int(self):
        self.assertEqual(institutional._to_int("1,234"), 1234)
        self.assertEqual(institutional._to_int("-8,251,130"), -8251130)
        self.assertEqual(institutional._to_int("--"), 0)
        self.assertEqual(institutional._to_int(None), 0)

    def test_as_date(self):
        self.assertEqual(
            institutional._as_date("20260911"), datetime.date(2026, 9, 11)
        )
        self.assertEqual(
            institutional._as_date("2026-09-11"), datetime.date(2026, 9, 11)
        )
        self.assertEqual(
            institutional._as_date("113/09/11"), datetime.date(2024, 9, 11)
        )

    def test_to_lots(self):
        self.assertEqual(institutional.to_lots(1000), 1.0)
        self.assertEqual(institutional.to_lots(-8251130), -8251.13)


class TWSEInstitutionalFetcherTest(unittest.TestCase):
    def test_make_row(self):
        fetcher = institutional.TWSEInstitutionalFetcher()
        day = datetime.date(2026, 9, 11)
        row = fetcher._make_row(day, TWSE_SAMPLE_ROW)
        self.assertEqual(row.code, "2330")
        self.assertEqual(row.name, "台積電")
        self.assertEqual(row.market, "twse")
        self.assertEqual(row.foreign_net, -8251130)
        self.assertEqual(row.trust_net, -180854)
        self.assertEqual(row.dealer_net, -400461)
        self.assertEqual(row.total_net, -8832445)
        self.assertIsNone(row.broker_detail)

    def test_fetch_ok(self):
        fetcher = institutional.TWSEInstitutionalFetcher()
        payload = {"stat": "OK", "data": [TWSE_SAMPLE_ROW]}
        with mock.patch.object(fetcher, "_session_get_json", return_value=payload):
            rows = fetcher.fetch("20260911")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].code, "2330")

    def test_fetch_empty_non_trading(self):
        fetcher = institutional.TWSEInstitutionalFetcher()
        payload = {"stat": "很抱歉，沒有符合條件的資料!", "total": 0}
        with mock.patch.object(fetcher, "_session_get_json", return_value=payload):
            rows = fetcher.fetch("20260914")
        self.assertEqual(rows, [])


class TPEXInstitutionalFetcherTest(unittest.TestCase):
    def test_make_row(self):
        fetcher = institutional.TPEXInstitutionalFetcher()
        day = datetime.date(2024, 9, 11)
        row = fetcher._make_row(day, TPEX_SAMPLE_ROW)
        self.assertEqual(row.code, "6223")
        self.assertEqual(row.market, "tpex")
        self.assertEqual(row.foreign_net, 327000)
        self.assertEqual(row.trust_net, 51000)
        self.assertEqual(row.dealer_self_net, 20026)
        self.assertEqual(row.dealer_hedge_net, 66038)
        self.assertEqual(row.dealer_net, 86064)
        self.assertEqual(row.total_net, 464064)
        self.assertEqual(
            row.foreign_net + row.foreign_dealer_net + row.trust_net + row.dealer_net,
            row.total_net,
        )

    def test_fetch_ok(self):
        fetcher = institutional.TPEXInstitutionalFetcher()
        payload = {"tables": [{"data": [TPEX_SAMPLE_ROW]}]}
        with mock.patch.object(fetcher, "_fetch_payload", return_value=payload):
            rows = fetcher.fetch("2024-09-11")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].code, "6223")


class FetchApiTest(unittest.TestCase):
    def test_fetch_both_markets(self):
        twse_rows = [
            institutional.Institutional(
                date=datetime.date(2026, 9, 11),
                market="twse",
                code="2330",
                name="台積電",
                foreign_buy=0,
                foreign_sell=0,
                foreign_net=0,
                foreign_dealer_buy=0,
                foreign_dealer_sell=0,
                foreign_dealer_net=0,
                trust_buy=0,
                trust_sell=0,
                trust_net=1000,
                dealer_self_buy=0,
                dealer_self_sell=0,
                dealer_self_net=0,
                dealer_hedge_buy=0,
                dealer_hedge_sell=0,
                dealer_hedge_net=0,
                dealer_net=0,
                total_net=1000,
                broker_detail=None,
            )
        ]
        tpex_rows = [
            institutional.Institutional(
                date=datetime.date(2026, 9, 11),
                market="tpex",
                code="6223",
                name="旺矽",
                foreign_buy=0,
                foreign_sell=0,
                foreign_net=0,
                foreign_dealer_buy=0,
                foreign_dealer_sell=0,
                foreign_dealer_net=0,
                trust_buy=0,
                trust_sell=0,
                trust_net=2000,
                dealer_self_buy=0,
                dealer_self_sell=0,
                dealer_self_net=0,
                dealer_hedge_buy=0,
                dealer_hedge_sell=0,
                dealer_hedge_net=0,
                dealer_net=0,
                total_net=2000,
                broker_detail=None,
            )
        ]
        with mock.patch.object(
            institutional.TWSEInstitutionalFetcher, "fetch", return_value=twse_rows
        ), mock.patch.object(
            institutional.TPEXInstitutionalFetcher, "fetch", return_value=tpex_rows
        ):
            rows = institutional.fetch("20260911")
        self.assertEqual([r.code for r in rows], ["2330", "6223"])
        top = institutional.top_by(rows, field="trust_net", limit=1)
        self.assertEqual(top[0].code, "6223")

    def test_unknown_market(self):
        with self.assertRaises(ValueError):
            institutional.fetch("20260911", markets=["foo"])


if __name__ == "__main__":
    unittest.main()
