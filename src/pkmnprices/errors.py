from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# Which limit a 429 hit. They clear on different clocks: per_minute within 60
# seconds, daily not until 00:00 UTC.
LimitType = Literal["per_minute", "daily"]


@dataclass
class RateLimitInfo:
    credits_charged: int | None = None
    # The plan's daily allowance.
    credits_limit: int | None = None
    # Credits left in today's allowance after this request.
    credits_remaining: int | None = None
    # Seconds until the allowance refills at 00:00 UTC.
    credits_reset: int | None = None
    # Prepaid credits left. Sent only while the account holds a balance.
    credits_balance: int | None = None
    rate_limit: int | None = None
    rate_remaining: int | None = None
    # Seconds until the per-minute window closes.
    rate_reset: int | None = None


class PkmnPricesError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status: int,
        code: str,
        docs_url: str | None = None,
        rate_limit: RateLimitInfo | None = None,
        retry_after: float | None = None,
        limit_type: LimitType | None = None,
        resets_at: str | None = None,
        upgrade_url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        # The docs page for this class of error, as sent by the API: a 401
        # points at authentication, a 403 at pricing, a 429 at rate limits.
        # None when the response carried no body to read it from.
        self.docs_url = docs_url
        self.rate_limit = rate_limit or RateLimitInfo()
        # Seconds until a retry can succeed.
        self.retry_after = retry_after
        # Set on a 429. None on every other error.
        self.limit_type = limit_type
        # On a 429, when the wait ends, RFC 3339 in UTC.
        self.resets_at = resets_at
        # On a daily-limit 429, the dashboard page for moving up a plan or
        # adding prepaid credits.
        self.upgrade_url = upgrade_url


class BadRequestError(PkmnPricesError): ...
class UnauthorizedError(PkmnPricesError): ...
class ForbiddenError(PkmnPricesError): ...
class NotFoundError(PkmnPricesError): ...
class ConflictError(PkmnPricesError): ...
class CreditLimitError(PkmnPricesError): ...
class RateLimitError(PkmnPricesError): ...
class InternalServerError(PkmnPricesError): ...


# Network failure, timeout, or a body that wasn't JSON. No HTTP status to map.
class APIConnectionError(PkmnPricesError):
    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message, status=0, code="connection_error")
        self.__cause__ = cause


_BY_STATUS: dict[int, type[PkmnPricesError]] = {
    400: BadRequestError,
    401: UnauthorizedError,
    403: ForbiddenError,
    404: NotFoundError,
    409: ConflictError,
}


def create_api_error(
    *,
    status: int,
    code: str,
    message: str,
    docs_url: str | None,
    rate_limit: RateLimitInfo,
    retry_after: float | None,
    limit_type: LimitType | None = None,
    resets_at: str | None = None,
    upgrade_url: str | None = None,
) -> PkmnPricesError:
    cls: type[PkmnPricesError]
    if status == 429:
        cls = CreditLimitError if code == "credit_limit_exceeded" else RateLimitError
    elif status >= 500:
        cls = InternalServerError
    else:
        cls = _BY_STATUS.get(status, PkmnPricesError)

    return cls(
        message,
        status=status,
        code=code,
        docs_url=docs_url,
        rate_limit=rate_limit,
        retry_after=retry_after,
        limit_type=limit_type,
        resets_at=resets_at,
        upgrade_url=upgrade_url,
    )
