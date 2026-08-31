"""Tests for canonical article assignment within duplicate groups."""

import asyncio
import re
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy.sql.dml import Update

from worker.tasks.scraping.article_cleanup import _assign_canonical_async


def _row(article_id: int, group_id: int, quality_score: float | None):
    return SimpleNamespace(id=article_id, duplicate_group_id=group_id, quality_score=quality_score)


def _ids_and_values(stmt: Update) -> tuple[list[int], dict]:
    """Extract target article ids and SET values from an UPDATE statement."""
    values = {}
    for col, bind in stmt._values.items():
        values[col.key] = getattr(bind, "value", bind)

    compiled = stmt.compile(compile_kwargs={"literal_binds": True})
    sql = str(compiled)
    ids: list[int] = []
    in_match = re.search(r"articles\.id\s+IN\s*\(([^)]+)\)", sql, re.IGNORECASE)
    eq_match = re.search(r"articles\.id\s*=\s*(\d+)", sql, re.IGNORECASE)
    if in_match:
        ids = [int(x.strip()) for x in in_match.group(1).split(",") if x.strip()]
    elif eq_match:
        ids = [int(eq_match.group(1))]
    return ids, values


class FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.updates: list[tuple[list[int], dict]] = []
        self.committed = False

    async def execute(self, stmt):
        if isinstance(stmt, Update):
            self.updates.append(_ids_and_values(stmt))
            return MagicMock()
        result = MagicMock()
        result.all.return_value = self.rows
        return result

    async def commit(self):
        self.committed = True


def _patch_session(fake: FakeSession):
    @asynccontextmanager
    async def _cm():
        yield fake

    return patch("worker.tasks.scraping.article_cleanup.async_session", new=lambda: _cm())


def _final_canonical_map(fake: FakeSession) -> dict[int, int | None]:
    """Replay captured UPDATEs onto a id -> canonical_article_id map."""
    state: dict[int, int | None] = {row.id: None for row in fake.rows}
    for ids, values in fake.updates:
        for article_id in ids:
            if "canonical_article_id" in values:
                state[article_id] = values["canonical_article_id"]
    return state


class TestAssignCanonicalArticles:
    def test_highest_quality_is_canonical_in_group_of_three(self):
        rows = [
            _row(1, 10, 0.40),
            _row(2, 10, 0.90),
            _row(3, 10, 0.55),
        ]
        fake = FakeSession(rows)
        with _patch_session(fake):
            result = asyncio.run(_assign_canonical_async())

        state = _final_canonical_map(fake)
        assert state[2] is None
        assert state[1] == 2
        assert state[3] == 2
        assert result["groups_processed"] == 1
        assert result["articles_updated"] == 2
        assert fake.committed

    def test_lower_quality_articles_point_to_canonical(self):
        rows = [
            _row(11, 7, 0.20),
            _row(12, 7, 0.80),
        ]
        fake = FakeSession(rows)
        with _patch_session(fake):
            asyncio.run(_assign_canonical_async())

        state = _final_canonical_map(fake)
        assert state[12] is None
        assert state[11] == 12

    def test_single_member_group_stays_canonical(self):
        rows = [_row(5, 99, 0.70)]
        fake = FakeSession(rows)
        with _patch_session(fake):
            result = asyncio.run(_assign_canonical_async())

        state = _final_canonical_map(fake)
        assert state[5] is None
        assert result["groups_processed"] == 1
        assert result["articles_updated"] == 0

    def test_null_quality_score_treated_as_half(self):
        # 0.40 vs NULL (treated as 0.5) → NULL article is canonical
        rows = [
            _row(21, 3, 0.40),
            _row(22, 3, None),
        ]
        fake = FakeSession(rows)
        with _patch_session(fake):
            asyncio.run(_assign_canonical_async())

        state = _final_canonical_map(fake)
        assert state[22] is None
        assert state[21] == 22

    def test_no_duplicate_groups_is_noop(self):
        fake = FakeSession([])
        with _patch_session(fake):
            result = asyncio.run(_assign_canonical_async())

        assert result == {"groups_processed": 0, "articles_updated": 0}
        assert fake.updates == []
        assert fake.committed is False

    def test_equal_quality_tie_does_not_crash(self):
        rows = [
            _row(31, 4, 0.60),
            _row(32, 4, 0.60),
        ]
        fake = FakeSession(rows)
        with _patch_session(fake):
            result = asyncio.run(_assign_canonical_async())

        state = _final_canonical_map(fake)
        canonical_ids = [aid for aid, canon in state.items() if canon is None]
        duplicate_ids = [aid for aid, canon in state.items() if canon is not None]
        assert len(canonical_ids) == 1
        assert len(duplicate_ids) == 1
        assert state[duplicate_ids[0]] == canonical_ids[0]
        assert result["groups_processed"] == 1
        assert result["articles_updated"] == 1
