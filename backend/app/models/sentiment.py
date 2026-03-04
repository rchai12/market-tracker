from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SentimentScore(Base):
    __tablename__ = "sentiment_scores"
    __table_args__ = (UniqueConstraint("article_id", "stock_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    stock_id: Mapped[int | None] = mapped_column(ForeignKey("stocks.id"), nullable=True)
    label: Mapped[str] = mapped_column(String(20), nullable=False)  # positive, negative, neutral
    positive_score: Mapped[float] = mapped_column(Numeric(6, 5), nullable=False)
    negative_score: Mapped[float] = mapped_column(Numeric(6, 5), nullable=False)
    neutral_score: Mapped[float] = mapped_column(Numeric(6, 5), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), default="finbert-v1")
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    article = relationship("Article", back_populates="sentiment_scores")
