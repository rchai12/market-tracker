from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TaskFailure(Base):
    __tablename__ = "task_failures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    task_args: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_kwargs: Mapped[str | None] = mapped_column(Text, nullable=True)
    exception_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    exception_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    traceback: Mapped[str | None] = mapped_column(Text, nullable=True)
    retries_exhausted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    failed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    retried_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
