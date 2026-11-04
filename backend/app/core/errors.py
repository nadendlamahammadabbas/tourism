"""RFC 7807 Problem Details error definitions and handlers."""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ProblemException(Exception):
    """Base exception complying with RFC 7807."""

    def __init__(
        self,
        status_code: int,
        title: str,
        detail: str,
        type_uri: str = "about:blank",
        instance: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.type_uri = type_uri
        self.instance = instance
        self.extra = extra or {}

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "type": self.type_uri,
            "title": self.title,
            "status": self.status_code,
            "detail": self.detail,
        }
        if self.instance:
            data["instance"] = self.instance
        data.update(self.extra)
        return data


def register_error_handlers(app: FastAPI) -> None:
    """Register RFC 7807 problem detail handlers on the FastAPI app."""

    @app.exception_handler(ProblemException)
    async def handle_problem_exception(request: Request, exc: ProblemException) -> JSONResponse:
        content = exc.to_dict()
        if not exc.instance:
            content["instance"] = str(request.url.path)
        return JSONResponse(
            status_code=exc.status_code,
            content=content,
            media_type="application/problem+json",
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        content = {
            "type": "about:blank",
            "title": exc.detail if isinstance(exc.detail, str) else "HTTP Exception",
            "status": exc.status_code,
            "detail": str(exc.detail),
            "instance": str(request.url.path),
        }
        return JSONResponse(
            status_code=exc.status_code,
            content=content,
            media_type="application/problem+json",
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        content = {
            "type": "https://smriti.archive/errors/validation-error",
            "title": "Request Validation Error",
            "status": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "detail": "One or more request parameters failed validation.",
            "instance": str(request.url.path),
            "invalid_params": exc.errors(),
        }
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=content,
            media_type="application/problem+json",
        )

