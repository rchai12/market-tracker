"""Phase 23b: yfinance insider DataFrame parsing and type mapping."""

from datetime import date

import pandas as pd

from worker.tasks.scraping.insider_data import map_transaction_type, parse_insider_dataframe


class TestMapTransactionType:
    def test_buy_and_purchase(self):
        assert map_transaction_type("Buy") == "P"
        assert map_transaction_type("Purchase") == "P"

    def test_sell_and_sale(self):
        assert map_transaction_type("Sell") == "S"
        assert map_transaction_type("Sale") == "S"

    def test_grant_is_award(self):
        assert map_transaction_type("Grant") == "A"
        assert map_transaction_type("Award") == "A"

    def test_unknown_is_none(self):
        assert map_transaction_type(None) is None
        assert map_transaction_type("Gift") is None


class TestParseInsiderDataframe:
    def test_filters_old_rows_and_maps_columns(self):
        df = pd.DataFrame(
            [
                {
                    "Start Date": "2026-09-01",
                    "Insider": "Tim Cook",
                    "Position": "CEO",
                    "Transaction": "Buy",
                    "Shares": 10000,
                    "Value": 1_895_000,
                },
                {
                    "Start Date": "2020-01-01",
                    "Insider": "Old Trade",
                    "Position": "CEO",
                    "Transaction": "Buy",
                    "Shares": 1,
                    "Value": 100,
                },
            ]
        )
        rows = parse_insider_dataframe(df, cutoff=date(2026, 6, 1))
        assert len(rows) == 1
        row = rows[0]
        assert row["insider_name"] == "Tim Cook"
        assert row["insider_title"] == "CEO"
        assert row["transaction_type"] == "P"
        assert row["shares"] == 10000.0
        assert abs(row["price_per_share"] - 189.5) < 1e-9
        assert row["transaction_date"] == date(2026, 9, 1)

    def test_empty_or_none_returns_empty(self):
        assert parse_insider_dataframe(None, date(2026, 1, 1)) == []
        assert parse_insider_dataframe(pd.DataFrame(), date(2026, 1, 1)) == []

    def test_skips_unmapped_type(self):
        df = pd.DataFrame(
            [
                {
                    "Start Date": "2026-09-01",
                    "Insider": "Someone",
                    "Position": "Director",
                    "Transaction": "Gift",
                    "Shares": 10,
                    "Value": 100,
                }
            ]
        )
        assert parse_insider_dataframe(df, cutoff=date(2026, 1, 1)) == []

    def test_type_column_alias(self):
        df = pd.DataFrame(
            [
                {
                    "Date": "2026-09-02",
                    "Insider": "CFO Name",
                    "Position": "CFO",
                    "Type": "Sale",
                    "Shares": 500,
                    "Value": 50_000,
                }
            ]
        )
        rows = parse_insider_dataframe(df, cutoff=date(2026, 1, 1))
        assert len(rows) == 1
        assert rows[0]["transaction_type"] == "S"
        assert rows[0]["insider_name"] == "CFO Name"
