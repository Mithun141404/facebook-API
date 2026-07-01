"""Pydantic schemas for publishing posts to Facebook."""
from datetime import datetime

from pydantic import Field, model_validator
from schemas.common import CamelModel


class PublishTextRequest(CamelModel):
    page_config_id: int = Field(..., description="DB ID of the page config to publish to")
    message: str = Field(..., min_length=1, description="Post text content")
    campaign_id: int | None = Field(default=None, description="Optional campaign to link this post to")
    scheduled_at: datetime | None = Field(
        default=None,
        description="UTC datetime to schedule the post. Must be 10+ min in the future, max 75 days.",
    )

    @model_validator(mode="after")
    def validate_schedule(self) -> "PublishTextRequest":
        if self.scheduled_at:
            from datetime import timezone
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            diff = (self.scheduled_at - now).total_seconds()
            if diff < 600:
                raise ValueError("Scheduled time must be at least 10 minutes in the future.")
            if diff > 75 * 24 * 3600:
                raise ValueError("Scheduled time cannot be more than 75 days in the future.")
        return self


class PublishPhotoRequest(CamelModel):
    page_config_id: int = Field(..., description="DB ID of the page config")
    caption: str | None = Field(default=None, description="Optional photo caption")
    campaign_id: int | None = None
    scheduled_at: datetime | None = None

    @model_validator(mode="after")
    def validate_schedule(self) -> "PublishPhotoRequest":
        if self.scheduled_at:
            from datetime import timezone
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            diff = (self.scheduled_at - now).total_seconds()
            if diff < 600:
                raise ValueError("Scheduled time must be at least 10 minutes in the future.")
            if diff > 75 * 24 * 3600:
                raise ValueError("Scheduled time cannot be more than 75 days in the future.")
        return self


class PublishResult(CamelModel):
    fb_post_id: str
    post_id: int | None = None          # local DB id if created immediately
    is_scheduled: bool = False
    message: str = "Published successfully"
