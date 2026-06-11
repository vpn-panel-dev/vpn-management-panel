import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    app.exception_handler(StarletteHTTPException)(http_exception_handler)
    app.exception_handler(RequestValidationError)(validation_exception_handler)
    app.exception_handler(Exception)(unhandled_exception_handler)


async def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={'detail': _http_detail(exc.status_code, exc.detail)},
        headers=exc.headers,
    )


async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    messages = [_validation_error_message(error) for error in exc.errors()]
    detail = 'Invalid request'
    if messages:
        joined_messages = '; '.join(messages)
        detail = f'{detail}: {joined_messages}'
    return JSONResponse(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, content={'detail': detail})


async def unhandled_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
    log.exception('Unhandled API error')
    return JSONResponse(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        content={'detail': 'Internal server error. Details were written to the server log.'},
    )


def _http_detail(status_code: int, detail: Any) -> str:
    if isinstance(detail, str) and detail:
        return detail
    if detail:
        return str(detail)
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return 'HTTP error'


def _validation_error_message(error: dict[str, Any]) -> str:
    location = _validation_location(error.get('loc'))
    message = str(error.get('msg') or 'Invalid value')
    if location:
        return f'{location}: {message}'
    return message


def _validation_location(location: Any) -> str:
    if not isinstance(location, tuple | list):
        return ''
    visible_parts = [str(part) for part in location if part not in {'body', 'query', 'path'}]
    return '.'.join(visible_parts)
