from typing import List, Optional, Dict, Any
"""Master v1 router — includes all sub-routers."""
from fastapi import APIRouter

from api.v1 import page_config, posts, campaigns, publish, webhooks, contacts

router = APIRouter(prefix="/api/v1")

router.include_router(page_config.router)
router.include_router(posts.router)
router.include_router(campaigns.router)
router.include_router(publish.router)
router.include_router(webhooks.router)
router.include_router(contacts.router)
