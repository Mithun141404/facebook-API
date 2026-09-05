from typing import List, Optional, Dict, Any
"""
Publish router — text posts, photo posts (file upload), and scheduled posts.
"""
import os
import json
import logging
from datetime import timezone, datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status, Query
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


IST = timezone(timedelta(hours=5, minutes=30))


def _scheduled_unix(scheduled_at: Optional[datetime]) -> Optional[int]:
    """Convert a naive IST datetime to a Unix timestamp for Facebook."""
    if not scheduled_at:
        return None
    if scheduled_at.tzinfo is None:
        # Treat naive datetimes as IST (UTC+5:30)
        return int(scheduled_at.replace(tzinfo=IST).timestamp())
    return int(scheduled_at.timestamp())


# ─── Text Post ────────────────────────────────────────────────────────────────


@router.post("/text", response_model=APIResponse[PublishResult])
async def publish_text(
    page_config_id: int = Form(..., description="DB ID of the page config"),
    message: str = Form(..., min_length=1, description="Post text content"),
    campaign_id: Optional[int] = Form(default=None),
    scheduled_at: Optional[datetime] = Form(default=None, description="UTC datetime (ISO 8601) to schedule"),
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

    local_id: Optional[int] = None
    if is_scheduled:
        # Persist to scheduled_posts.json so /publish/scheduled can list it
        posts = _load_scheduled_posts()
        posts.append({
            "id": fb_post_id,
            "page_config_id": page_config_id,
            "campaign_id": campaign_id,
            "message": message,
            "scheduled_unix": sched_unix,
            "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
            "type": "text",
            "state": "scheduled",
        })
        _save_scheduled_posts(posts)
    elif fb_post_id:
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
from typing import Optional



@router.post("/photo", response_model=APIResponse[PublishResult])
async def publish_photo(
    page_config_id: int = Form(..., description="DB ID of the page config"),
    image: UploadFile = File(..., description="Image file to upload (JPEG, PNG, GIF, WEBP)"),
    message: Optional[str] = Form(default=None, description="Optional caption for the photo"),
    campaign_id: Optional[int] = Form(default=None),
    scheduled_at: Optional[datetime] = Form(default=None, description="UTC datetime (ISO 8601) to schedule"),
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
            caption=message or "",
            scheduled_unix=sched_unix,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    # Facebook /photos returns both 'id' (photo ID) and 'post_id' (feed post ID).
    # Always prefer post_id for local tracking so it matches what /fetch returns.
    fb_post_id = result.get("post_id") or result.get("id", "")
    is_scheduled = bool(sched_unix)

    local_id: Optional[int] = None
    if is_scheduled:
        # Persist to scheduled_posts.json so /publish/scheduled can list it
        posts = _load_scheduled_posts()
        posts.append({
            "id": fb_post_id,
            "page_config_id": page_config_id,
            "campaign_id": campaign_id,
            "message": message or "",
            "scheduled_unix": sched_unix,
            "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
            "type": "photo",
            "state": "scheduled",
        })
        _save_scheduled_posts(posts)
    elif fb_post_id:
        post = Post(
            fb_post_id=fb_post_id,
            page_config_id=config.id,
            campaign_id=campaign_id,
            message=message or "",
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


# ─── Scheduled Posts ──────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
JSON_FILE_PATH = os.path.join(BASE_DIR, "scheduled_posts.json")

def _load_scheduled_posts() -> List[Dict[str, Any]]:
    if not os.path.exists(JSON_FILE_PATH):
        return []
    with open(JSON_FILE_PATH, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def _save_scheduled_posts(posts: List[Dict[str, Any]]):
    with open(JSON_FILE_PATH, "w") as f:
        json.dump(posts, f, indent=4)

@router.get("/scheduled", response_model=APIResponse[List[Dict[str, Any]]])
async def list_scheduled_posts(page_config_id: Optional[int] = Query(None, description="Optional page config ID to filter by")):
    """
    List Scheduled Posts.
    Reads scheduled_posts.json, optionally filters by page_config_id,
    and safely strips the access_token.
    """
    posts = _load_scheduled_posts()
    
    if page_config_id is not None:
        posts = [p for p in posts if str(p.get("page_config_id")) == str(page_config_id)]
        
    for p in posts:
        p.pop("access_token", None)
        
    return APIResponse(data=posts, message="Scheduled posts retrieved.")

@router.delete("/scheduled/{post_id}", response_model=APIResponse[None])
async def remove_scheduled_post(post_id: str):
    """
    Remove Scheduled Post.
    Only deletes the post if its current state is 'scheduled'.
    """
    posts = _load_scheduled_posts()
    
    post_index = None
    for i, p in enumerate(posts):
        if str(p.get("id", "")) == post_id or str(p.get("post_id", "")) == post_id:
            post_index = i
            break
            
    if post_index is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Scheduled post not found or already published"
        )
        
    post = posts[post_index]
    
    if post.get("state") != "scheduled":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Scheduled post not found or already published"
        )
        
    posts.pop(post_index)
    _save_scheduled_posts(posts)
    
    return APIResponse(message="Scheduled post removed.")
