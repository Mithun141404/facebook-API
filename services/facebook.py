from typing import List, Optional, Dict, Any
"""
All Facebook Graph API calls are centralised here.
These are pure async functions — no DB access, no FastAPI concerns.
"""
import io
import logging
from datetime import datetime

import httpx

from config import settings

_logger = logging.getLogger(__name__)

GRAPH_BASE = settings.fb_graph_base_url


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _parse_fb_datetime(raw: Optional[str]) -> Optional[datetime]:
    """Parse a Facebook ISO 8601 datetime string to a naive UTC datetime."""
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None)
    except ValueError:
        _logger.warning("Could not parse FB datetime: %s", raw)
        return None


def _raise_for_fb_error(response: httpx.Response) -> None:
    """Raise a descriptive ValueError on non-2xx Facebook responses."""
    if response.is_error:
        try:
            err = response.json().get("error", {})
            msg = err.get("message", response.text)
        except Exception:
            msg = response.text
        raise ValueError(f"Facebook API error ({response.status_code}): {msg}")


# ─── Posts ────────────────────────────────────────────────────────────────────


async def fetch_posts(page_id: str, access_token: str, limit: int = 25) -> List[dict]:
    """
    Fetch posts from a Facebook Page using the Graph API.
    Returns a list of post dicts ready for upsert into the DB.
    """
    url = f"{GRAPH_BASE}/{page_id}/posts"
    params = {
        "fields": "id,message,created_time,full_picture,permalink_url,likes.summary(true)",
        "access_token": access_token,
        "limit": min(limit, 100),
    }

    posts: List[dict] = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        while url:
            response = await client.get(url, params=params)
            _raise_for_fb_error(response)
            data = response.json()

            for item in data.get("data", []):
                like_summary = item.get("likes", {}).get("summary", {})
                posts.append(
                    {
                        "fb_post_id": item.get("id"),
                        "message": item.get("message", ""),
                        "published_date": _parse_fb_datetime(item.get("created_time")),
                        "permalink_url": item.get("permalink_url", ""),
                        "image_url": item.get("full_picture", ""),
                        "like_count": like_summary.get("total_count", 0),
                    }
                )

            # Cursor-based pagination — follow until no more pages
            paging = data.get("paging", {})
            next_url = paging.get("next")
            # Only follow if we haven't hit the limit yet
            if next_url and len(posts) < limit:
                url = next_url
                params = {}   # next_url already contains all params
            else:
                break

    _logger.info("Fetched %d posts for page_id=%s", len(posts), page_id)
    return posts


async def delete_post(fb_post_id: str, access_token: str) -> dict:
    """
    Delete a post from Facebook Graph API permanently.
    """
    url = f"{GRAPH_BASE}/{fb_post_id}"
    params = {"access_token": access_token}

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.delete(url, params=params)
        _raise_for_fb_error(response)
        
    result = response.json()
    _logger.info("Deleted post %s from Facebook — result: %s", fb_post_id, result)
    return result


async def edit_post(fb_post_id: str, access_token: str, message: str) -> dict:
    """
    Edit the caption of an existing post on Facebook.
    """
    url = f"{GRAPH_BASE}/{fb_post_id}"
    payload = {
        "message": message,
        "access_token": access_token,
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, data=payload)
        _raise_for_fb_error(response)
        
    result = response.json()
    _logger.info("Edited post %s on Facebook — result: %s", fb_post_id, result)
    return result


# ─── Comments ─────────────────────────────────────────────────────────────────


async def fetch_comments(fb_post_id: str, access_token: str, limit: int = 50) -> List[dict]:
    """
    Fetch top-level comments for a single post.
    Returns a list of comment dicts ready for upsert.
    """
    url = f"{GRAPH_BASE}/{fb_post_id}/comments"
    params = {
        "fields": "id,message,from,created_time,like_count",
        "access_token": access_token,
        "limit": limit,
        "filter": "stream",
        "summary": "true",
    }

    comments: List[dict] = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url, params=params)
        _raise_for_fb_error(response)
        data = response.json()

        for item in data.get("data", []):
            comments.append(
                {
                    "fb_comment_id": item.get("id"),
                    "author_name": item.get("from", {}).get("name", ""),
                    "message": item.get("message", ""),
                    "published_date": _parse_fb_datetime(item.get("created_time")),
                    "like_count": item.get("like_count", 0),
                }
            )

    _logger.info("Fetched %d comments for post_id=%s", len(comments), fb_post_id)
    return comments


# ─── Publish: Text ────────────────────────────────────────────────────────────


async def publish_text_post(
    page_id: str,
    access_token: str,
    message: str,
    scheduled_unix: Optional[int] = None,
) -> dict:
    """
    Publish a plain-text post to a Facebook Page feed.
    If scheduled_unix is provided, the post will be scheduled.
    Returns the Graph API response dict (contains 'id').
    """
    url = f"{GRAPH_BASE}/{page_id}/feed"
    payload = {
        "message": message,
        "access_token": access_token,
    }
    if scheduled_unix:
        payload["published"] = "false"
        payload["scheduled_publish_time"] = str(scheduled_unix)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, data=payload)
        _raise_for_fb_error(response)

    result = response.json()
    _logger.info("Published text post to page %s — result: %s", page_id, result)
    return result


# ─── Publish: Photo ───────────────────────────────────────────────────────────
from typing import Optional, List



async def publish_photo_post(
    page_id: str,
    access_token: str,
    image_bytes: bytes,
    filename: str,
    caption: str = "",
    scheduled_unix: Optional[int] = None,
) -> dict:
    """
    Publish a photo post to a Facebook Page.
    image_bytes — raw image binary (from the uploaded file).
    Returns the Graph API response dict (contains 'id' and 'post_id').
    """
    url = f"{GRAPH_BASE}/{page_id}/photos"

    # Determine MIME type from filename extension
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    mime_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }
    mime_type = mime_map.get(ext, "image/jpeg")

    data = {"access_token": access_token}
    if caption:
        data["caption"] = caption
    if scheduled_unix:
        data["published"] = "false"
        data["scheduled_publish_time"] = str(scheduled_unix)

    files = {"source": (filename, io.BytesIO(image_bytes), mime_type)}

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, data=data, files=files)
        _raise_for_fb_error(response)

    result = response.json()
    _logger.info("Published photo post to page %s — result: %s", page_id, result)
    return result
