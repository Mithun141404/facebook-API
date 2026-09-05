from typing import List, Optional, Dict, Any
"""
Page Config router — CRUD for Facebook Page credentials + manual fetch trigger.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import require_api_key
from db.base import get_db
from db.models import PageConfig, Post, Comment
from schemas.common import APIResponse
from schemas.page_config import (
    FetchResult,
    PageConfigCreate,
    PageConfigOut,
    PageConfigUpdate,
)
from services.encryption import decrypt_token, encrypt_token
from services.facebook import fetch_comments, fetch_posts

router = APIRouter(prefix="/page-configs", tags=["Page Configs"])
_logger = logging.getLogger(__name__)


# ─── CRUD ────────────────────────────────────────────────────────────────────


@router.get("", response_model=APIResponse[List[PageConfigOut]])
async def list_page_configs(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """List all Facebook Page configurations."""
    result = await db.execute(select(PageConfig).order_by(PageConfig.id))
    configs = result.scalars().all()
    return APIResponse(data=[PageConfigOut.model_validate(c) for c in configs])


@router.post("", response_model=APIResponse[PageConfigOut], status_code=status.HTTP_201_CREATED)
async def create_page_config(
    payload: PageConfigCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Create a new Facebook Page configuration."""
    # Check for duplicate page_id among active configs only
    existing = await db.execute(
        select(PageConfig).where(
            PageConfig.page_id == payload.page_id,
            PageConfig.active == True,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An active page config for page_id '{payload.page_id}' already exists.",
        )

    config = PageConfig(
        page_name=payload.page_name,
        page_id=payload.page_id,
        access_token=encrypt_token(payload.access_token),
        post_limit=payload.post_limit,
        active=payload.active,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return APIResponse(message="Page config created.", data=PageConfigOut.model_validate(config))


@router.get("/{config_id}", response_model=APIResponse[PageConfigOut])
async def get_page_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Get a single page configuration by ID."""
    config = await db.get(PageConfig, config_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page config not found.")
    return APIResponse(data=PageConfigOut.model_validate(config))


@router.put("/{config_id}", response_model=APIResponse[PageConfigOut])
async def update_page_config(
    config_id: int,
    payload: PageConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Update a page configuration."""
    config = await db.get(PageConfig, config_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page config not found.")

    updates = payload.model_dump(exclude_none=True)
    if "access_token" in updates:
        updates["access_token"] = encrypt_token(updates["access_token"])

    for key, value in updates.items():
        setattr(config, key, value)

    await db.commit()
    await db.refresh(config)
    return APIResponse(message="Page config updated.", data=PageConfigOut.model_validate(config))


@router.delete("/{config_id}", response_model=APIResponse[None])
async def delete_page_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Delete a page configuration and all its associated posts."""
    config = await db.get(PageConfig, config_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page config not found.")
    await db.delete(config)
    await db.commit()
    return APIResponse(message="Page config deleted.")


# ─── Fetch Trigger ────────────────────────────────────────────────────────────
from typing import Optional, List



@router.post("/{config_id}/fetch", response_model=APIResponse[FetchResult])
async def fetch_posts_for_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """
    Trigger a Facebook post fetch for a specific page config.
    Fetches posts + comments from the Graph API and upserts into the local DB.
    """
    config = await db.get(PageConfig, config_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page config not found.")
    if not config.active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Page config is inactive.")

    plain_token = decrypt_token(config.access_token)

    try:
        raw_posts = await fetch_posts(config.page_id, plain_token, config.post_limit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    posts_created = posts_updated = comments_fetched = 0

    for raw in raw_posts:
        fb_id = raw["fb_post_id"]
        existing_result = await db.execute(select(Post).where(Post.fb_post_id == fb_id))
        existing: Optional[Post] = existing_result.scalar_one_or_none()

        if existing:
            existing.message = raw["message"]
            existing.published_date = raw["published_date"]
            existing.permalink_url = raw["permalink_url"]
            existing.image_url = raw["image_url"]
            existing.like_count = raw["like_count"]
            existing.active = True
            post_record = existing
            posts_updated += 1
        else:
            post_record = Post(
                fb_post_id=fb_id,
                page_config_id=config.id,
                message=raw["message"],
                published_date=raw["published_date"],
                permalink_url=raw["permalink_url"],
                image_url=raw["image_url"],
                like_count=raw["like_count"],
            )
            db.add(post_record)
            await db.flush()   # get post_record.id before fetching comments
            posts_created += 1

        # Fetch comments for each post
        try:
            raw_comments = await fetch_comments(fb_id, plain_token)
            for rc in raw_comments:
                c_id = rc["fb_comment_id"]
                existing_c_result = await db.execute(
                    select(Comment).where(Comment.fb_comment_id == c_id)
                )
                existing_c: Optional[Comment] = existing_c_result.scalar_one_or_none()

                if existing_c:
                    existing_c.message = rc["message"]
                    existing_c.like_count = rc["like_count"]
                    existing_c.published_date = rc["published_date"]
                else:
                    comment = Comment(
                        fb_comment_id=c_id,
                        post_id=post_record.id,
                        author_name=rc["author_name"],
                        message=rc["message"],
                        published_date=rc["published_date"],
                        like_count=rc["like_count"],
                    )
                    db.add(comment)
                    comments_fetched += 1

            # Update comment count on the post
            post_record.comment_count = len(raw_comments)

        except ValueError as exc:
            _logger.warning("Failed to fetch comments for post %s: %s", fb_id, exc)

    await db.commit()

    result = FetchResult(
        page_id=config.page_id,
        page_name=config.page_name,
        posts_fetched=len(raw_posts),
        posts_created=posts_created,
        posts_updated=posts_updated,
        comments_fetched=comments_fetched,
    )
    return APIResponse(message="Fetch complete.", data=result)


@router.post("/fetch-all", response_model=APIResponse[List[FetchResult]])
async def fetch_all_active_pages(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """
    Trigger a post fetch for ALL active page configurations.
    Called by the CRM when it wants to sync everything at once.
    """
    result = await db.execute(select(PageConfig).where(PageConfig.active == True))
    configs = result.scalars().all()

    if not configs:
        return APIResponse(message="No active page configs found.", data=[])

    results: List[FetchResult] = []

    for config in configs:
        plain_token = decrypt_token(config.access_token)
        try:
            raw_posts = await fetch_posts(config.page_id, plain_token, config.post_limit)
        except ValueError as exc:
            results.append(
                FetchResult(
                    page_id=config.page_id,
                    page_name=config.page_name,
                    posts_fetched=0,
                    posts_created=0,
                    posts_updated=0,
                    comments_fetched=0,
                    error=str(exc),
                )
            )
            continue

        posts_created = posts_updated = comments_fetched = 0
        for raw in raw_posts:
            fb_id = raw["fb_post_id"]
            existing_result = await db.execute(select(Post).where(Post.fb_post_id == fb_id))
            existing = existing_result.scalar_one_or_none()

            if existing:
                existing.message = raw["message"]
                existing.published_date = raw["published_date"]
                existing.permalink_url = raw["permalink_url"]
                existing.image_url = raw["image_url"]
                existing.like_count = raw["like_count"]
                post_record = existing
                posts_updated += 1
            else:
                post_record = Post(
                    fb_post_id=fb_id,
                    page_config_id=config.id,
                    message=raw["message"],
                    published_date=raw["published_date"],
                    permalink_url=raw["permalink_url"],
                    image_url=raw["image_url"],
                    like_count=raw["like_count"],
                )
                db.add(post_record)
                await db.flush()
                posts_created += 1

            try:
                raw_comments = await fetch_comments(fb_id, plain_token)
                for rc in raw_comments:
                    c_id = rc["fb_comment_id"]
                    existing_c_result = await db.execute(
                        select(Comment).where(Comment.fb_comment_id == c_id)
                    )
                    existing_c = existing_c_result.scalar_one_or_none()
                    if existing_c:
                        existing_c.message = rc["message"]
                        existing_c.like_count = rc["like_count"]
                    else:
                        db.add(Comment(
                            fb_comment_id=c_id,
                            post_id=post_record.id,
                            author_name=rc["author_name"],
                            message=rc["message"],
                            published_date=rc["published_date"],
                            like_count=rc["like_count"],
                        ))
                        comments_fetched += 1
                post_record.comment_count = len(raw_comments)
            except ValueError as exc:
                _logger.warning("Comment fetch failed for %s: %s", fb_id, exc)

        await db.commit()
        results.append(FetchResult(
            page_id=config.page_id,
            page_name=config.page_name,
            posts_fetched=len(raw_posts),
            posts_created=posts_created,
            posts_updated=posts_updated,
            comments_fetched=comments_fetched,
        ))

    return APIResponse(message="Fetch all complete.", data=results)
