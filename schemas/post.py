from typing import List, Optional, Dict, Any
"""Pydantic schemas for Facebook Posts and Comments."""
from typing import Optional, List

from datetime import datetime

from pydantic import Field
from schemas.common import CamelModel


class CommentOut(CamelModel):
    id: int
    fb_comment_id: str
    author_name: Optional[str]
    message: Optional[str]
    published_date: Optional[datetime]
    like_count: int


class PostOut(CamelModel):
    id: int
    fb_post_id: str
    page_config_id: int
    campaign_id: Optional[int]
    message: Optional[str]
    published_date: Optional[datetime]
    permalink_url: Optional[str]
    image_url: Optional[str]
    like_count: int
    comment_count: int
    active: bool
    created_at: datetime
    updated_at: datetime


class PostDetail(PostOut):
    """Extended post schema that includes comments."""
    comments: List[CommentOut] = []


class PostAssignCampaign(CamelModel):
    campaign_id: int = Field(..., description="ID of the campaign to assign")


class PostEdit(CamelModel):
    message: str = Field(..., description="The new text/caption for the post")


class PostListFilters(CamelModel):
    page_config_id: Optional[int] = None
    campaign_id: Optional[int] = None
    active: Optional[bool] = True
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)
