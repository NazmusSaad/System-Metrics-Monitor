"""FastAPI application entry point."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import router
from app.collector import collector_loop
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

stop_event = asyncio.Event()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = None
    if settings.enable_local_collector:
        logger.info("Starting local metrics collector for '%s'", settings.machine_name)
        task = asyncio.create_task(collector_loop(stop_event))
    else:
        logger.info("Local collector disabled (ENABLE_LOCAL_COLLECTOR=false)")
    yield
    if task is not None:
        logger.info("Shutting down collector")
        stop_event.set()
        await task


app = FastAPI(title="System Metrics Monitor", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
