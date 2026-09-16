"""Typed v2 error envelope models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

V2_VALIDATION_ERROR_EXAMPLE: dict[str, Any] = {
    "error": {
        "code": "validation_error",
        "message": "Request validation failed.",
        "details": [
            {
                "field": "budget_total",
                "message": "Input should be greater than 0",
                "code": "greater_than",
            }
        ],
    }
}

V2_NOT_FOUND_ERROR_EXAMPLE: dict[str, Any] = {
    "error": {
        "code": "not_found",
        "message": "Trip or task was not found.",
        "details": [],
    }
}

V2_CONFLICT_ERROR_EXAMPLE: dict[str, Any] = {
    "error": {
        "code": "conflict",
        "message": "Idempotency-Key has already been used with a different request payload.",
        "details": [],
    }
}

V2_INTERNAL_ERROR_EXAMPLE: dict[str, Any] = {
    "error": {
        "code": "internal_server_error",
        "message": "An unexpected server error occurred.",
        "details": [],
    }
}


class ErrorDetailV2(BaseModel):
    """Single validation or HTTP error detail."""

    model_config = ConfigDict(json_schema_extra={"example": V2_VALIDATION_ERROR_EXAMPLE["error"]["details"][0]})

    field: str | None = Field(default=None, description="Field path when available.")
    message: str = Field(..., description="Human-readable error detail.")
    code: str = Field(..., description="Machine-readable detail code.")


class ErrorBodyV2(BaseModel):
    """Body of the v2 error envelope."""

    code: str = Field(..., description="Top-level error code.")
    message: str = Field(..., description="Top-level error message.")
    details: list[ErrorDetailV2] = Field(default_factory=list, description="Optional error details.")


class ErrorEnvelopeV2(BaseModel):
    """Consistent top-level error envelope for /api/v2 routes."""

    model_config = ConfigDict(json_schema_extra={"example": V2_VALIDATION_ERROR_EXAMPLE})

    error: ErrorBodyV2 = Field(..., description="Wrapped error payload.")


def build_error_envelope(
    *,
    code: str,
    message: str,
    details: list[ErrorDetailV2] | None = None,
) -> ErrorEnvelopeV2:
    """Construct a typed v2 error envelope."""
    return ErrorEnvelopeV2(error=ErrorBodyV2(code=code, message=message, details=details or []))
