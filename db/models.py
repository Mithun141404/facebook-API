"""
SQLAlchemy ORM models — all four core tables.
Uses Optional[X] syntax for Python 3.14 compatibility with SQLAlchemy 2.0.x.
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class PageConfig(Base):
    """Stores a Facebook Page's credentials (ID + encrypted access token)."""

    __tablename__ = "fb_page_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    page_name: Mapped[str] = mapped_column(String(255), nullable=False)
    page_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)   # stored encrypted
    post_limit: Mapped[int] = mapped_column(Integer, default=25)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    posts: Mapped[List["Post"]] = relationship("Post", back_populates="page_config", cascade="all, delete-orphan")


class Campaign(Base):
    """Groups posts under a named marketing campaign."""

    __tablename__ = "fb_campaign"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    posts: Mapped[List["Post"]] = relationship("Post", back_populates="campaign")

    # Computed stats (cached — recalculated on sync)
    post_count: Mapped[int] = mapped_column(Integer, default=0)
    engagement: Mapped[int] = mapped_column(Integer, default=0)  # likes + comments


class Post(Base):
    """A Facebook Page post fetched from the Graph API."""

    __tablename__ = "fb_post"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fb_post_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    page_config_id: Mapped[int] = mapped_column(Integer, ForeignKey("fb_page_config.id", ondelete="CASCADE"), nullable=False)
    campaign_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("fb_campaign.id", ondelete="SET NULL"), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    permalink_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    page_config: Mapped["PageConfig"] = relationship("PageConfig", back_populates="posts")
    campaign: Mapped[Optional["Campaign"]] = relationship("Campaign", back_populates="posts")
    comments: Mapped[List["Comment"]] = relationship("Comment", back_populates="post", cascade="all, delete-orphan")


class Comment(Base):
    """A top-level comment on a Facebook post."""

    __tablename__ = "fb_comment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fb_comment_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("fb_post.id", ondelete="CASCADE"), nullable=False)
    author_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    post: Mapped["Post"] = relationship("Post", back_populates="comments")
