"""Audit logging helper for admin actions."""

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


async def record_audit(
    db: AsyncSession,
    user_id: int | None,
    action: str,
    resource: str,
    detail: dict | str | None = None,
    ip_address: str | None = None,
) -> None:
    """Record an audit log entry.

    Args:
        db: Active database session.
        user_id: ID of the user performing the action (None for system actions).
        action: Short action label, e.g. "trigger_scrape", "create_api_key".
        resource: Resource path, e.g. "admin/scrape-now".
        detail: Optional JSON-serializable detail about the action.
        ip_address: Client IP address.
    """
    detail_str = json.dumps(detail, default=str) if isinstance(detail, dict) else detail
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        detail=detail_str,
        ip_address=ip_address,
    )
    db.add(entry)
    await db.flush()
    logger.debug("Audit: user=%s action=%s resource=%s", user_id, action, resource)
