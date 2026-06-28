import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .error_handlers import register_error_handlers
from .routers import api, auth, internal_worker, remnawave, telegram_proxy, user_page

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield


app = FastAPI(title='AmneziaWG Panel', lifespan=lifespan)
register_error_handlers(app)
app.include_router(auth.router)
app.include_router(api.webhook_router)
app.include_router(api.router)
app.include_router(internal_worker.router)
app.include_router(remnawave.router)
app.include_router(telegram_proxy.router)
app.include_router(user_page.router)
