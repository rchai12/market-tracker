from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router
from app.config import settings
from app.core.logging_config import setup_logging
from app.core.middleware import RequestLoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level)
    from app.core.cache import close_cache_pool, init_cache_pool
    from app.core.slow_query import attach_slow_query_listener
    from app.database import engine

    await init_cache_pool()
    attach_slow_query_listener(engine)
    yield
    await close_cache_pool()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Stock Predictor API",
        description="Sentiment-driven stock market prediction system",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    )
    app.add_middleware(RequestLoggingMiddleware)

    app.include_router(router)

    return app


app = create_app()
