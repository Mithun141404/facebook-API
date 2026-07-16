from typing import List, Optional, Dict, Any
"""
Contacts router — acts as a proxy to forward requests to Laravel.
"""
import httpx
import logging
from fastapi import APIRouter, Request, Response

from config import settings

router = APIRouter(prefix="/contacts", tags=["Contacts"])
_logger = logging.getLogger(__name__)

async def proxy_request(request: Request, path: str):
    # Map FastAPI's GET /api/v1/contacts to Laravel's GET /api/contacts/list
    target_path = f"/api/contacts/list" if not path else f"/api/contact/{path}"
    target_url = f"{settings.laravel_backend_url.rstrip('/')}{target_path}"
    
    headers = dict(request.headers)
    for h in ["host", "content-length", "transfer-encoding", "connection", "keep-alive"]:
        headers.pop(h, None)
    
    body = await request.body()
    
    async with httpx.AsyncClient() as client:
        try:
            proxy_response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                params=request.query_params,
                content=body,
            )
            
            resp_headers = dict(proxy_response.headers)
            for h in ["content-encoding", "content-length", "transfer-encoding", "connection"]:
                resp_headers.pop(h, None)
                
            return Response(
                content=proxy_response.content,
                status_code=proxy_response.status_code,
                headers=resp_headers
            )
        except httpx.RequestError as e:
            _logger.error(f"Error proxying to Laravel: {e}")
            return Response(status_code=502, content="Bad Gateway")

@router.api_route("", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def handle_contacts(request: Request, path: str = ""):
    """Proxy all contacts requests to the Laravel backend."""
    return await proxy_request(request, path)
