from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_url: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    key_phrases: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    event_category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    duplicate_group_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)

    article_stocks = relationship("ArticleStock", back_populates="article", cascade="all, delete-orphan")
    sentiment_scores = relationship("SentimentScore", back_populates="article", cascade="all, delete-orphan")


class ArticleStock(Base):
    __tablename__ = "article_stocks"

    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), primary_key=True)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), default=1.0)

    article = relationship("Article", back_populates="article_stocks")
    stock = relationship("Stock", back_populates="article_stocks")
