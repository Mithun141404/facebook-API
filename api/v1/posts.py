from typing import List, Optional, Dict, Any
"""
Posts router — list, get, assign campaign, soft-delete.
Comments are nested under posts.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.deps import require_api_key
from db.base import get_db
from db.models import Comment, Post, PageConfig
from schemas.common import APIResponse
from schemas.post import CommentOut, PostAssignCampaign, PostDetail, PostOut, PostEdit
from services.encryption import decrypt_token
from services.facebook import delete_post as fb_delete_post, edit_post as fb_edit_post

router = APIRouter(prefix="/posts", tags=["Posts"])
_logger = logging.getLogger(__name__)


@router.get("", response_model=APIResponse[List[PostOut]])
async def list_posts(
    page_config_id: Optional[int] = Query(default=None, alias="pageConfigId"),
    campaign_id: Optional[int] = Query(default=None, alias="campaignId"),
    active: Optional[bool] = Query(default=True),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """
    List posts with optional filters.
    - Filter by page_config_id, campaign_id, or active status.
    """
    query = select(Post)
    if page_config_id is not None:
        query = query.where(Post.page_config_id == page_config_id)
    if campaign_id is not None:
        query = query.where(Post.campaign_id == campaign_id)
    if active is not None:
        query = query.where(Post.active == active)

    query = query.order_by(Post.published_date.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    posts = result.scalars().all()
    return APIResponse(data=[PostOut.model_validate(p) for p in posts])


@router.get("/{post_id}", response_model=APIResponse[PostDetail])
async def get_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Get a single post with all its comments."""
    result = await db.execute(
        select(Post)
        .options(selectinload(Post.comments))
        .where(Post.id == post_id)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")

    detail = PostDetail.model_validate(post)
    detail.comments = [CommentOut.model_validate(c) for c in post.comments]
    return APIResponse(data=detail)


@router.put("/{post_id}/campaign", response_model=APIResponse[PostOut])
async def assign_campaign(
    post_id: int,
    payload: PostAssignCampaign,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Assign a post to a campaign."""
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")

    post.campaign_id = payload.campaign_id
    await db.commit()
    await db.refresh(post)
    return APIResponse(message="Campaign assigned.", data=PostOut.model_validate(post))


@router.delete("/{post_id}", response_model=APIResponse[None])
async def delete_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Soft-delete a post (sets active=False) and delete it from Facebook permanently."""
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")

    page_config = await db.get(PageConfig, post.page_config_id)
    if not page_config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page config not found.")

    plain_token = decrypt_token(page_config.access_token)
    try:
        await fb_delete_post(post.fb_post_id, plain_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    post.active = False
    await db.commit()
    return APIResponse(message="Post deactivated locally and deleted permanently from Facebook.")


@router.patch("/{post_id}", response_model=APIResponse[PostOut])
async def edit_post_endpoint(
    post_id: int,
    payload: PostEdit,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Edit the caption/message of an existing post on Facebook and locally."""
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")

    page_config = await db.get(PageConfig, post.page_config_id)
    if not page_config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page config not found.")

    plain_token = decrypt_token(page_config.access_token)
    try:
        await fb_edit_post(post.fb_post_id, plain_token, payload.message)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    post.message = payload.message
    await db.commit()
    await db.refresh(post)
    return APIResponse(message="Post edited successfully.", data=PostOut.model_validate(post))


# ─── Comments sub-resource ───────────────────────────────────────────────────
from typing import Optional, List



@router.get("/{post_id}/comments", response_model=APIResponse[List[CommentOut]])
async def list_comments(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """List all comments for a post."""
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")

    result = await db.execute(
        select(Comment)
        .where(Comment.post_id == post_id)
        .order_by(Comment.published_date.asc())
    )
    comments = result.scalars().all()
    return APIResponse(data=[CommentOut.model_validate(c) for c in comments])
