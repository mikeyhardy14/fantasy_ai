"""Application-level exceptions.

Services raise these; the API layer maps them to HTTP responses in one place
(see app.main.register_exception_handlers).
"""


class AppError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str | None = None, *, details: dict | None = None):
        self.message = message or self.__class__.__doc__ or self.code
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(AppError):
    """Resource not found."""

    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    """Resource already exists."""

    status_code = 409
    code = "conflict"


class UnauthorizedError(AppError):
    """Authentication required or invalid."""

    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    """You do not have access to this resource."""

    status_code = 403
    code = "forbidden"


class ValidationFailed(AppError):
    """Request could not be processed."""

    status_code = 422
    code = "validation_failed"


class ServiceUnavailableError(AppError):
    """An upstream service is unavailable."""

    status_code = 503
    code = "service_unavailable"


# ---- Provider errors -------------------------------------------------------


class ProviderError(AppError):
    """Fantasy provider request failed."""

    status_code = 502
    code = "provider_error"

    def __init__(self, message: str | None = None, *, provider: str | None = None, **kw):
        super().__init__(message, **kw)
        if provider:
            self.details.setdefault("provider", provider)


class ProviderNotFound(ProviderError):
    """The requested user or league does not exist on the provider."""

    status_code = 404
    code = "provider_not_found"


class ProviderRateLimited(ProviderError):
    """The provider is rate limiting requests. Try again shortly."""

    status_code = 429
    code = "provider_rate_limited"


class ProviderUnavailable(ProviderError):
    """The provider could not be reached."""

    status_code = 502
    code = "provider_unavailable"


class ProviderAuthError(ProviderError):
    """Provider credentials are missing or invalid."""

    status_code = 401
    code = "provider_auth_error"


class ProviderNotImplemented(ProviderError):
    """This fantasy provider is not supported yet."""

    status_code = 501
    code = "provider_not_implemented"


class AIUnavailable(AppError):
    """AI features are not configured on this server."""

    status_code = 503
    code = "ai_unavailable"
