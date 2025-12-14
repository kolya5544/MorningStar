# app/main.py
import os
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from app.routers.health import router as health_router
from app.routers.portfolios import router as v1_portfolios
from app.routers.integrations import router as integrations_router
from app.routers.market import router as market_router

from app.db import engine
from app.orm_models import Base

app = FastAPI(title=os.getenv("SERVICE_NAME", "morningstar-api"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

@app.on_event("startup")
def _startup():
    Base.metadata.create_all(bind=engine)

@app.get("/")
def root():
    return {"service": "morningstar-api", "message": "OK"}

app.include_router(health_router, prefix="/api/health", tags=["health"])

v1 = APIRouter(prefix="/api/v1", tags=["v1"])
v1.include_router(v1_portfolios)
v1.include_router(integrations_router)
v1.include_router(market_router)
app.include_router(v1)
