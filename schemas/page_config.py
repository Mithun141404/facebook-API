"""Pydantic schemas for Facebook Page Configurations."""
from datetime import datetime

from pydantic import Field
from schemas.common import CamelModel


class PageConfigCreate(CamelModel):
    page_name: str = Field(..., min_length=1, max_length=255, examples=["My Business Page"])
    page_id: str = Field(..., min_length=1, max_length=100, examples=["123456789"])
    access_token: str = Field(..., min_length=10, examples=["EAAxxxxxxx..."])
    post_limit: int = Field(default=25, ge=1, le=100)
    active: bool = True


class PageConfigUpdate(CamelModel):
    page_name: str | None = Field(default=None, max_length=255)
    access_token: str | None = None
    post_limit: int | None = Field(default=None, ge=1, le=100)
    active: bool | None = None


class PageConfigOut(CamelModel):
    id: int
    page_name: str
    page_id: str
    post_limit: int
    active: bool
    created_at: datetime
    updated_at: datetime


class FetchResult(CamelModel):
    page_id: str
    page_name: str
    posts_fetched: int
    posts_created: int
    posts_updated: int
    comments_fetched: int
    error: str | None = None
