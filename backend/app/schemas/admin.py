"""Schemas for admin-only endpoints: task failures, audit logs."""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import PaginationMeta


class TaskFailureResponse(BaseModel):
    id: int
    task_name: str
    task_args: str | None = None
    task_kwargs: str | None = None
    exception_type: str | None = None
    exception_message: str | None = None
    traceback: str | None = None
    retries_exhausted: bool
    failed_at: datetime
    retried_at: datetime | None = None
    retry_task_id: str | None = None

    model_config = {"from_attributes": True}


class PaginatedTaskFailures(BaseModel):
    data: list[TaskFailureResponse]
    meta: PaginationMeta


class AuditLogResponse(BaseModel):
    id: int
    user_id: int | None = None
    action: str
    resource: str
    detail: str | None = None
    ip_address: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedAuditLogs(BaseModel):
    data: list[AuditLogResponse]
    meta: PaginationMeta
