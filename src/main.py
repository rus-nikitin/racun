from typing import AsyncGenerator
from contextlib import asynccontextmanager, AsyncExitStack
from fastapi import FastAPI

from src.config import settings
from src.logging_config import setup_logging

from src.router import api_router

from src.db import db_lifespan
from src.client import client_lifespan
from src.middleware import RequestIDMiddleware


@asynccontextmanager
async def combined_lifespan(app: FastAPI) -> AsyncGenerator:
    async with AsyncExitStack() as stack:
        for lifespan_func in [db_lifespan, client_lifespan]:
            await stack.enter_async_context(lifespan_func(app))
        yield


app: FastAPI = FastAPI(
    lifespan=combined_lifespan,
    title=settings.project_name,
)

app.add_middleware(RequestIDMiddleware)
app.include_router(api_router, prefix=settings.api_prefix)


def main():
    try:
        import uvicorn

        setup_logging()

        uvicorn.run("main:app", host=settings.host, port=settings.port)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
