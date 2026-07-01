"""
Campaigns router — CRUD + live stats aggregation.
"""
import logging

from fastapi import APIRouter, Depends, Form, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import require_api_key
from db.base import get_db
from db.models import Campaign, Post
from schemas.campaign import CampaignCreate, CampaignOut, CampaignStats, CampaignUpdate
from schemas.common import APIResponse

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])
_logger = logging.getLogger(__name__)


@router.get("", response_model=APIResponse[list[CampaignOut]])
async def list_campaigns(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """List all campaigns with cached stats."""
    result = await db.execute(select(Campaign).order_by(Campaign.created_at.desc()))
    campaigns = result.scalars().all()
    return APIResponse(data=[CampaignOut.model_validate(c) for c in campaigns])


@router.post("", response_model=APIResponse[CampaignOut], status_code=status.HTTP_201_CREATED)
async def create_campaign(
    name: str = Form(..., min_length=1, max_length=255),
    description: str | None = Form(default=None),
    active: bool = Form(default=True),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Create a new campaign."""
    campaign = Campaign(
        name=name,
        description=description,
        active=active,
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return APIResponse(message="Campaign created.", data=CampaignOut.model_validate(campaign))


@router.get("/{campaign_id}", response_model=APIResponse[CampaignOut])
async def get_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Get a single campaign."""
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")
    return APIResponse(data=CampaignOut.model_validate(campaign))


@router.put("/{campaign_id}", response_model=APIResponse[CampaignOut])
async def update_campaign(
    campaign_id: int,
    name: str | None = Form(default=None, max_length=255),
    description: str | None = Form(default=None),
    active: bool | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Update a campaign's name/description/active status."""
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    if name is not None:
        campaign.name = name
    if description is not None:
        campaign.description = description
    if active is not None:
        campaign.active = active

    await db.commit()
    await db.refresh(campaign)
    return APIResponse(message="Campaign updated.", data=CampaignOut.model_validate(campaign))


@router.delete("/{campaign_id}", response_model=APIResponse[None])
async def delete_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Delete a campaign. Posts linked to it will have campaign_id set to NULL."""
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")
    await db.delete(campaign)
    await db.commit()
    return APIResponse(message="Campaign deleted.")


@router.get("/{campaign_id}/stats", response_model=APIResponse[CampaignStats])
async def get_campaign_stats(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """
    Compute live aggregated stats for a campaign:
    total posts, total likes, total comments, total engagement.
    Also refreshes the cached post_count and engagement on the campaign record.
    """
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    result = await db.execute(
        select(
            func.count(Post.id).label("post_count"),
            func.coalesce(func.sum(Post.like_count), 0).label("like_count"),
            func.coalesce(func.sum(Post.comment_count), 0).label("comment_count"),
        ).where(Post.campaign_id == campaign_id, Post.active == True)
    )
    row = result.one()
    like_count = int(row.like_count)
    comment_count = int(row.comment_count)
    post_count = int(row.post_count)
    engagement = like_count + comment_count

    # Refresh cached stats on the campaign record
    campaign.post_count = post_count
    campaign.engagement = engagement
    await db.commit()

    return APIResponse(
        data=CampaignStats(
            post_count=post_count,
            engagement=engagement,
            like_count=like_count,
            comment_count=comment_count,
        )
    )
