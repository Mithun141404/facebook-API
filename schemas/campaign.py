"""Pydantic schemas for Campaigns."""
from datetime import datetime

from pydantic import Field
from schemas.common import CamelModel


class CampaignCreate(CamelModel):
    name: str = Field(..., min_length=1, max_length=255, examples=["Summer Sale 2025"])
    description: str | None = None
    active: bool = True


class CampaignUpdate(CamelModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    active: bool | None = None


class CampaignStats(CamelModel):
    post_count: int
    engagement: int   # total likes + comments across all posts
    like_count: int
    comment_count: int


class CampaignOut(CamelModel):
    id: int
    name: str
    description: str | None
    active: bool
    post_count: int
    engagement: int
    created_at: datetime
    updated_at: datetime
