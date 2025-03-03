from contextlib import asynccontextmanager
import httpx

from fastapi import Request, FastAPI

from logging import getLogger

log = getLogger(__name__)


@asynccontextmanager
async def client_lifespan(app: FastAPI):
    app.async_client = httpx.AsyncClient(timeout=10)

    log.info("Created async client.")

    yield

    await app.async_client.aclose()
    log.info("Closed async client connection.")


def get_async_client(request: Request):
    return request.app.async_client
