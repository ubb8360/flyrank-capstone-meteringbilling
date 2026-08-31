from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class GenerateRequest(BaseModel):
    usage_type: Literal["api_call", "ai_tokens"]

    input_tokens: int | None = Field(default=None, ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_usage(self):
        if self.usage_type == "api_call":
            return self

        token_values = [
            self.input_tokens,
            self.cached_input_tokens,
            self.output_tokens,
            self.reasoning_tokens,
        ]

        if all(value is None for value in token_values):
            raise ValueError(
                "AI token usage requires at least one token value."
            )

        return self


class GenerateResponse(BaseModel):
    event_id: UUID
    usage_type: str
    quantity: int
    cost_microusd: int
    idempotency_key: str

    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None