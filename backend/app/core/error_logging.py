"""Central JSON error logging for the API, scheduler, and SMTP client."""

from contextvars import ContextVar
from datetime import UTC, datetime
import base64
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re
import traceback
from urllib.parse import quote, quote_plus
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from app.core.config import BACKEND_DIR, Settings


request_context: ContextVar[dict] = ContextVar("error_log_request", default={})
logger = logging.getLogger(__name__)


class ErrorJsonFormatter(logging.Formatter):
    def __init__(self, secrets: tuple[str, ...] = ()):
        super().__init__()
        self.secrets = sorted({value for value in secrets if value}, key=len, reverse=True)

    def redact(self, text: str) -> str:
        for value in self.secrets:
            text = text.replace(value, "[REDACTED]")
        return re.sub(
            r"(?i)\b(password|passwd|pwd|authorization|access_token|refresh_token)\b"
            r"(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;]+)",
            r"\1\2[REDACTED]", text,
        )

    def exception_details(self, error: BaseException, seen: set[int] | None = None) -> dict:
        seen = set() if seen is None else seen
        seen.add(id(error))
        # SQLAlchemy exception strings include SQL and bound payroll data. Pydantic
        # validation strings include submitted values. Neither belongs in this log.
        message = (
            "Database statement and parameters omitted."
            if isinstance(error, SQLAlchemyError) else
            "Validation input omitted."
            if isinstance(error, ValidationError) else str(error)
        )
        result = {
            "type": type(error).__name__,
            "message": self.redact(message),
            "stack": [
                {"file": frame.filename, "line": frame.lineno, "function": frame.name}
                for frame in traceback.extract_tb(error.__traceback__)
            ],
        }
        cause = error.__cause__ or (None if error.__suppress_context__ else error.__context__)
        if cause is not None and id(cause) not in seen:
            result["cause"] = self.exception_details(cause, seen)
        return result

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": self.redact(record.getMessage()),
            "source": {"file": record.pathname, "line": record.lineno, "function": record.funcName},
            "process_id": record.process,
            "thread": record.threadName,
            **request_context.get(),
        }
        for field in ("job_id", "smtp_code", "smtp_response", "status_code"):
            if hasattr(record, field):
                value = getattr(record, field)
                entry[field] = self.redact(value) if isinstance(value, str) else value
        if record.exc_info and record.exc_info[1] is not None:
            entry["exception"] = self.exception_details(record.exc_info[1])
        return json.dumps(entry, ensure_ascii=False, default=str)


class CentralErrorHandler(RotatingFileHandler):
    """Marker class lets reload/setup replace only handlers owned by this app."""


class CentralErrorConsoleHandler(logging.StreamHandler):
    """Keep application failures visible in the terminal as well as the file."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Uvicorn already has its own terminal handler.
        return not record.name.startswith("uvicorn.") and record.name != "uvicorn"


def configure_error_logging(settings: Settings) -> Path:
    path = settings.error_log_file
    if not path.is_absolute():
        path = BACKEND_DIR / path
    path.parent.mkdir(parents=True, exist_ok=True)
    secrets = []
    for value in (settings.db_password, settings.mail_password.get_secret_value()):
        if value:
            secrets.extend((value, quote(value, safe=""), quote_plus(value), base64.b64encode(value.encode()).decode()))
    password = settings.mail_password.get_secret_value()
    if password:
        secrets.append(base64.b64encode(f"\0{settings.mail_username}\0{password}".encode()).decode())
    handler = CentralErrorHandler(
        path, maxBytes=settings.error_log_max_bytes, backupCount=settings.error_log_backup_count,
        encoding="utf-8", errors="backslashreplace",
    )
    handler.setLevel(logging.WARNING)
    formatter = ErrorJsonFormatter(tuple(secrets))
    handler.setFormatter(formatter)
    root = logging.getLogger()
    for previous in list(root.handlers):
        if isinstance(previous, CentralErrorHandler):
            root.removeHandler(previous)
            previous.close()
    root.addHandler(handler)
    for existing in root.handlers:
        if isinstance(existing, CentralErrorConsoleHandler):
            existing.setFormatter(formatter)
    if not any(isinstance(existing, logging.StreamHandler) and not isinstance(existing, logging.FileHandler) for existing in root.handlers):
        console = CentralErrorConsoleHandler()
        console.setLevel(logging.WARNING)
        console.setFormatter(formatter)
        root.addHandler(console)
    if root.level > logging.WARNING:
        root.setLevel(logging.WARNING)
    # Uvicorn normally stops propagation at its console logger.
    logging.getLogger("uvicorn").propagate = True
    logging.getLogger("uvicorn.error").propagate = True
    logging.captureWarnings(True)
    return path


class ErrorRequestContextMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        token = request_context.set({
            "request_id": str(uuid4()), "method": scope["method"], "path": scope["path"],
        })

        async def log_error_response(message):
            if message["type"] == "http.response.start" and message["status"] >= 400 and not scope.get("_ecs_error_logged"):
                code = message["status"]
                logger.log(
                    logging.ERROR if code >= 500 else logging.WARNING,
                    "HTTP request failed with status %s.", code, extra={"status_code": code},
                )
            await send(message)

        try:
            await self.app(scope, receive, log_error_response)
        except Exception:
            logger.exception("Unhandled request failure.", extra={"status_code": 500})
            raise
        finally:
            request_context.reset(token)


def install_error_handlers(app: FastAPI) -> None:
    app.add_middleware(ErrorRequestContextMiddleware)

    @app.exception_handler(HTTPException)
    async def log_http_error(request: Request, error: HTTPException):
        request.scope["_ecs_error_logged"] = True
        logger.log(
            logging.ERROR if error.status_code >= 500 else logging.WARNING,
            "HTTP request failed with status %s.", error.status_code,
            exc_info=(type(error), error, error.__traceback__), extra={"status_code": error.status_code},
        )
        return await http_exception_handler(request, error)

    @app.exception_handler(RequestValidationError)
    async def log_validation_error(request: Request, error: RequestValidationError):
        # Preserve FastAPI's response; never log the submitted body or input values.
        request.scope["_ecs_error_logged"] = True
        logger.warning("Request validation failed.", extra={"status_code": 422})
        return await request_validation_exception_handler(request, error)
