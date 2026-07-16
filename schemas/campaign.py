from typing import List, Optional, Dict, Any
"""Pydantic schemas for Campaigns."""
from typing import Optional

from datetime import datetime

from pydantic import Field
from schemas.common import CamelModel


class CampaignCreate(CamelModel):
    name: str = Field(..., min_length=1, max_length=255, examples=["Summer Sale 2025"])
    description: Optional[str] = None
    active: bool = True


class CampaignUpdate(CamelModel):
    name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    active: Optional[bool] = None


class CampaignStats(CamelModel):
    post_count: int
    engagement: int   # total likes + comments across all posts
    like_count: int
    comment_count: int


class CampaignOut(CamelModel):
    id: int
    name: str
    description: Optional[str]
    active: bool
    post_count: int
    engagement: int
    created_at: datetime
    updated_at: datetime
