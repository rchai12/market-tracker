"""Tests for the audit logging helper."""

import asyncio
from unittest.mock import AsyncMock

from app.core.audit import record_audit


class TestRecordAudit:
    """Tests for the record_audit helper."""

    def test_creates_audit_entry(self):
        async def _test():
            mock_db = AsyncMock()
            await record_audit(db=mock_db, user_id=1, action="trigger_scrape", resource="admin/scrape-now")
            return mock_db

        mock_db = asyncio.run(_test())
        mock_db.add.assert_called_once()
        entry = mock_db.add.call_args[0][0]
        assert entry.user_id == 1
        assert entry.action == "trigger_scrape"
        assert entry.resource == "admin/scrape-now"
        assert entry.detail is None

    def test_dict_detail_serialized_to_json(self):
        async def _test():
            mock_db = AsyncMock()
            await record_audit(db=mock_db, user_id=1, action="seed_history", resource="admin/seed-history", detail={"period": "max"})
            return mock_db

        mock_db = asyncio.run(_test())
        entry = mock_db.add.call_args[0][0]
        assert entry.detail == '{"period": "max"}'

    def test_string_detail_passed_through(self):
        async def _test():
            mock_db = AsyncMock()
            await record_audit(db=mock_db, user_id=1, action="test", resource="test/resource", detail="plain text detail")
            return mock_db

        mock_db = asyncio.run(_test())
        entry = mock_db.add.call_args[0][0]
        assert entry.detail == "plain text detail"

    def test_ip_address_recorded(self):
        async def _test():
            mock_db = AsyncMock()
            await record_audit(db=mock_db, user_id=1, action="test", resource="test", ip_address="192.168.1.1")
            return mock_db

        mock_db = asyncio.run(_test())
        entry = mock_db.add.call_args[0][0]
        assert entry.ip_address == "192.168.1.1"

    def test_system_action_null_user(self):
        async def _test():
            mock_db = AsyncMock()
            await record_audit(db=mock_db, user_id=None, action="system_cleanup", resource="system")
            return mock_db

        mock_db = asyncio.run(_test())
        entry = mock_db.add.call_args[0][0]
        assert entry.user_id is None
