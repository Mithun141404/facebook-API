"""Pydantic schemas for Facebook Posts and Comments."""
from datetime import datetime

from pydantic import Field
from schemas.common import CamelModel


class CommentOut(CamelModel):
    id: int
    fb_comment_id: str
    author_name: str | None
    message: str | None
    published_date: datetime | None
    like_count: int


class PostOut(CamelModel):
    id: int
    fb_post_id: str
    page_config_id: int
    campaign_id: int | None
    message: str | None
    published_date: datetime | None
    permalink_url: str | None
    image_url: str | None
    like_count: int
    comment_count: int
    active: bool
    created_at: datetime
    updated_at: datetime


class PostDetail(PostOut):
    """Extended post schema that includes comments."""
    comments: list[CommentOut] = []


class PostAssignCampaign(CamelModel):
    campaign_id: int = Field(..., description="ID of the campaign to assign")


class PostListFilters(CamelModel):
    page_config_id: int | None = None
    campaign_id: int | None = None
    active: bool | None = True
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)
