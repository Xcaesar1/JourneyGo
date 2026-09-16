"""Sanitized research-provider failures."""

from __future__ import annotations

from ...domain.research_models import ProviderErrorCode


class ResearchProviderError(Exception):
    """Base error whose string form is always safe to persist or return."""

    error_code: ProviderErrorCode = "unavailable"
    safe_message = "Research provider is unavailable."

    def __init__(self) -> None:
        super().__init__(self.safe_message)


class ProviderAuthenticationError(ResearchProviderError):
    error_code = "authentication"
    safe_message = "Research provider authentication failed."


class ProviderRateLimitError(ResearchProviderError):
    error_code = "rate_limited"
    safe_message = "Research provider rate limit was reached."


class ProviderTimeoutError(ResearchProviderError):
    error_code = "timeout"
    safe_message = "Research provider timed out."


class ProviderInvalidResponseError(ResearchProviderError):
    error_code = "invalid_response"
    safe_message = "Research provider returned an invalid response."


class ProviderUnavailableError(ResearchProviderError):
    error_code = "unavailable"
    safe_message = "Research provider is unavailable."
