from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RateLimitInfo:
    credits_charged: int | None = None
    credits_limit: int | None = None
    rate_limit: int | None = None
    rate_remaining: int | None = None


class PkmnPricesError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status: int,
        code: str,
        rate_limit: RateLimitInfo | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.rate_limit = rate_limit or RateLimitInfo()
        self.retry_after = retry_after


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
    rate_limit: RateLimitInfo,
    retry_after: float | None,
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
        rate_limit=rate_limit,
        retry_after=retry_after,
    )
