from typing import List, Optional, Dict, Any
"""
Shared FastAPI dependencies.
"""
import logging

from fastapi import Header, HTTPException, status

from config import settings

_logger = logging.getLogger(__name__)


async def require_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    """
    Validates the X-API-Key header on every protected route.
    The CRM must send this header on all requests to this service.
    """
    if x_api_key != settings.api_key:
        _logger.warning("Rejected request with invalid API key.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )
    return x_api_key
