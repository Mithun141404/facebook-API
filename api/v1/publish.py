"""
Publish router — text posts, photo posts (file upload), and scheduled posts.
"""
import logging
from datetime import timezone, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import require_api_key
from db.base import get_db
from db.models import PageConfig, Post
from schemas.common import APIResponse
from schemas.publish import PublishResult
from services.encryption import decrypt_token
from services.facebook import publish_photo_post, publish_text_post

router = APIRouter(prefix="/publish", tags=["Publish"])
_logger = logging.getLogger(__name__)

# Maximum upload size: 10 MB
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024


async def _get_config(config_id: int, db: AsyncSession) -> PageConfig:
    """Fetch and validate a page config by ID."""
    config = await db.get(PageConfig, config_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page config not found.")
    if not config.active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Page config is inactive.")
    return config


def _scheduled_unix(scheduled_at: datetime | None) -> int | None:
    """Convert a naive UTC datetime to a Unix timestamp for Facebook."""
    if not scheduled_at:
        return None
    if scheduled_at.tzinfo is None:
        # Treat as UTC
        return int(scheduled_at.replace(tzinfo=timezone.utc).timestamp())
    return int(scheduled_at.timestamp())


# ─── Text Post ────────────────────────────────────────────────────────────────


@router.post("/text", response_model=APIResponse[PublishResult])
async def publish_text(
    page_config_id: int = Form(..., alias="pageConfigId", description="DB ID of the page config"),
    message: str = Form(..., min_length=1, description="Post text content"),
    campaign_id: int | None = Form(default=None, alias="campaignId"),
    scheduled_at: datetime | None = Form(default=None, alias="scheduledAt", description="UTC datetime (ISO 8601) to schedule"),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """
    Publish a text-only post to a Facebook Page.
    If scheduled_at is provided, the post will be scheduled (must be 10+ min in the future).
    """
    config = await _get_config(page_config_id, db)
    plain_token = decrypt_token(config.access_token)
    sched_unix = _scheduled_unix(scheduled_at)

    try:
        result = await publish_text_post(
            page_id=config.page_id,
            access_token=plain_token,
            message=message,
            scheduled_unix=sched_unix,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    fb_post_id = result.get("id", "")
    is_scheduled = bool(sched_unix)

    local_id: int | None = None
    if not is_scheduled and fb_post_id:
        # Immediately create a local record so the CRM can reference it
        post = Post(
            fb_post_id=fb_post_id,
            page_config_id=config.id,
            campaign_id=campaign_id,
            message=message,
            active=True,
        )
        db.add(post)
        await db.commit()
        await db.refresh(post)
        local_id = post.id

    return APIResponse(
        message="Post scheduled." if is_scheduled else "Post published.",
        data=PublishResult(
            fb_post_id=fb_post_id,
            post_id=local_id,
            is_scheduled=is_scheduled,
            message="Post scheduled — it will go live at the specified time." if is_scheduled else "Post published successfully.",
        ),
    )


# ─── Photo Post ───────────────────────────────────────────────────────────────


@router.post("/photo", response_model=APIResponse[PublishResult])
async def publish_photo(
    page_config_id: int = Form(..., alias="pageConfigId", description="DB ID of the page config"),
    image: UploadFile = File(..., description="Image file to upload (JPEG, PNG, GIF, WEBP)"),
    caption: str | None = Form(default=None, description="Optional caption for the photo"),
    campaign_id: int | None = Form(default=None, alias="campaignId"),
    scheduled_at: datetime | None = Form(default=None, alias="scheduledAt", description="UTC datetime (ISO 8601) to schedule"),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """
    Publish a photo post to a Facebook Page.
    Accepts a multipart image file upload directly from the CRM.
    """
    # Validate file type
    allowed_types = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if image.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported image type '{image.content_type}'. Use JPEG, PNG, GIF, or WEBP.",
        )

    # Read and size-check the file
    image_bytes = await image.read()
    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image exceeds 10 MB limit.",
        )

    config = await _get_config(page_config_id, db)
    plain_token = decrypt_token(config.access_token)
    sched_unix = _scheduled_unix(scheduled_at)

    try:
        result = await publish_photo_post(
            page_id=config.page_id,
            access_token=plain_token,
            image_bytes=image_bytes,
            filename=image.filename or "photo.jpg",
            caption=caption or "",
            scheduled_unix=sched_unix,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    # Facebook /photos returns both 'id' (photo ID) and 'post_id' (feed post ID).
    # Always prefer post_id for local tracking so it matches what /fetch returns.
    fb_post_id = result.get("post_id") or result.get("id", "")
    is_scheduled = bool(sched_unix)

    local_id: int | None = None
    if not is_scheduled and fb_post_id:
        post = Post(
            fb_post_id=fb_post_id,
            page_config_id=config.id,
            campaign_id=campaign_id,
            message=caption or "",
            active=True,
        )
        db.add(post)
        await db.commit()
        await db.refresh(post)
        local_id = post.id

    return APIResponse(
        message="Photo scheduled." if is_scheduled else "Photo published.",
        data=PublishResult(
            fb_post_id=fb_post_id,
            post_id=local_id,
            is_scheduled=is_scheduled,
            message="Photo scheduled — it will go live at the specified time." if is_scheduled else "Photo published successfully.",
        ),
    )
