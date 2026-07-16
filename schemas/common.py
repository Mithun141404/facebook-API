from typing import List, Optional, Dict, Any
"""Shared response envelope and base schemas."""
from typing import Optional

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

T = TypeVar("T")


class CamelModel(BaseModel):
    """Base model that automatically converts snake_case to camelCase."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class APIResponse(CamelModel, Generic[T]):
    """Standard JSON envelope for all API responses."""
    success: bool = True
    message: str = "OK"
    data: Optional[T] = None


class ErrorResponse(CamelModel):
    success: bool = False
    message: str
    detail: Optional[Any] = None
