"""Uniform JSON errors with human-readable Russian messages."""
from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        self.status, self.code, self.message, self.details = status, code, message, details or {}


def _body(code: str, message: str, details=None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def _ru_validation(err: dict) -> str:
    loc = [str(x) for x in err.get("loc", []) if x not in ("query", "path", "body")]
    name = loc[-1] if loc else "параметр"
    t = err.get("type", "")
    ctx = err.get("ctx") or {}
    if t == "missing":
        return f"Не указан обязательный параметр «{name}»"
    if t in ("int_parsing", "int_type", "int_from_float"):
        return f"Параметр «{name}» должен быть целым числом"
    if t in ("float_parsing", "float_type"):
        return f"Параметр «{name}» должен быть числом"
    if t == "greater_than_equal":
        return f"Параметр «{name}» должен быть не меньше {ctx.get('ge')}"
    if t == "less_than_equal":
        return f"Параметр «{name}» должен быть не больше {ctx.get('le')}"
    if t in ("literal_error", "enum"):
        return f"Недопустимое значение параметра «{name}». Допустимо: {str(ctx.get('expected', '')).replace(' or ', ', ')}"
    return f"Некорректное значение параметра «{name}»"


def install(app) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return ORJSONResponse(_body(exc.code, exc.message, exc.details), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        errs = exc.errors()
        msgs = [_ru_validation(e) for e in errs]
        details = {"errors": [{"param": str((e.get("loc") or ["?"])[-1]), "message": m} for e, m in zip(errs, msgs)]}
        return ORJSONResponse(_body("validation_error", "; ".join(msgs), details), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        msg = {404: "Ресурс не найден", 405: "Метод не поддерживается"}.get(exc.status_code, str(exc.detail))
        return ORJSONResponse(_body(f"http_{exc.status_code}", msg), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        return ORJSONResponse(_body("internal_error", "Внутренняя ошибка сервиса. Попробуйте позже."), status_code=500)
