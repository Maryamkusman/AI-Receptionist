import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from . import config
from .db import Base, SessionLocal, engine
from .models import Salon
from .routes import api, webhooks
from .workers.scheduler import job_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        empty = db.scalar(select(Salon)) is None
    if empty:
        from .seed import seed
        seed()
    task = asyncio.create_task(job_loop())
    yield
    task.cancel()


app = FastAPI(title="FullChair API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.DASHBOARD_ORIGIN, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"], allow_headers=["*"],
)
app.include_router(api.router)
app.include_router(webhooks.router)


@app.get("/health")
def health():
    return {"ok": True, "ai": config.ai_enabled()}
