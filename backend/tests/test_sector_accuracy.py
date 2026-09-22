"""Sector accuracy grouping, thin-row hiding, and sector filter SQL."""

from sqlalchemy.dialects import postgresql

from app.api.daily_view_accuracy import _apply_view_filters, _base_select
from worker.utils.daily_accuracy import AccuracyRow, aggregate_by_label, visible_group_rows


class TestSectorAccuracy:
    def test_groups_and_sorts_by_sector(self):
        rows = [
            AccuracyRow(0.4, True, 0.02, sector="Technology"),
            AccuracyRow(0.5, True, 0.01, sector="Technology"),
            AccuracyRow(0.3, False, -0.01, sector="Energy"),
            AccuracyRow(0.4, True, 0.03, sector="Energy"),
        ]
        sectors = {s["sector"]: s for s in aggregate_by_label(rows, "sector")}
        assert sectors["Technology"]["count"] == 2
        assert sectors["Technology"]["accuracy_pct"] == 100.0
        assert sectors["Energy"]["accuracy_pct"] == 50.0
        assert list(s["sector"] for s in aggregate_by_label(rows, "sector")) == ["Energy", "Technology"]

    def test_hides_rows_below_five(self):
        rows = [
            *[AccuracyRow(0.4, True, 0.01, sector="Technology") for _ in range(5)],
            *[AccuracyRow(0.4, True, 0.01, sector="Energy") for _ in range(4)],
        ]
        grouped = aggregate_by_label(rows, "sector")
        visible = visible_group_rows(grouped, min_count=5)
        assert [s["sector"] for s in visible] == ["Technology"]

    def test_sector_param_added_to_query(self):
        stmt = _apply_view_filters(
            _base_select(1, True),
            sector="Technology",
            direction=None,
            date_from=None,
            date_to=None,
            min_conviction=0.20,
        )
        sql = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})).lower()
        assert "window_days" in sql
        assert "0.2" in sql or "0.20" in sql
        assert "technology" in sql
        assert "sector" in sql
