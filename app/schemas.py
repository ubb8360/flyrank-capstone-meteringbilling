from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class GenerateRequest(BaseModel):
    usage_type: Literal["api_call"] = "api_call"


class GenerateResponse(BaseModel):
    event_id: UUID
    usage_type: str
    quantity: int
    cost_microusd: int
    idempotency_key: str