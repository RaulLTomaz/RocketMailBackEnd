from typing import Any, Optional
from pydantic import BaseModel

class ErrorDetail(BaseModel):
    code: int
    message: str
    context: Optional[Any] = None

class ErrorResponse(BaseModel):
    detail: str
    error: ErrorDetail
