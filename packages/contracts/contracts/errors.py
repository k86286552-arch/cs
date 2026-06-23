from __future__ import annotations

from pydantic import BaseModel


ERROR_CODES = {
    "NEWS_SEARCH_FAILED",
    "ARTICLE_NOT_FOUND",
    "ARTICLE_PARSE_FAILED",
    "PDF_DOWNLOAD_FAILED",
    "PDF_TOO_LARGE",
    "RESOURCE_TABLE_NOT_FOUND",
    "RESOURCE_EXTRACTION_FAILED",
    "UNSUPPORTED_COMMODITY",
    "PRICE_NOT_FOUND",
    "PRICE_PROVIDER_UNAVAILABLE",
    "INVALID_ARGUMENT",
    "RATE_LIMITED",
    "INTERNAL_ERROR",
}

RETRYABLE_CODES = {
    "NEWS_SEARCH_FAILED",
    "PDF_DOWNLOAD_FAILED",
    "PRICE_PROVIDER_UNAVAILABLE",
    "RATE_LIMITED",
    "INTERNAL_ERROR",
}


class ToolError(BaseModel):
    error_code: str
    message: str
    retryable: bool = False
    component: str = ""
    details: dict = {}

    @classmethod
    def from_code(cls, code: str, message: str, component: str = "", **details) -> "ToolError":
        return cls(
            error_code=code,
            message=message,
            retryable=code in RETRYABLE_CODES,
            component=component,
            details=details,
        )