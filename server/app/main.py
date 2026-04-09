import os

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from app.auth import AuthMiddleware, require_user
from app.db import engine
from app.orm_models import Base
from app.routers.auth import router as auth_router
from app.routers.file_downloads import router as file_downloads_router
from app.routers.health import router as health_router
from app.routers.integrations import router as integrations_router
from app.routers.market import router as market_router
from app.routers.portfolios import router as portfolios_router

load_dotenv()

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost").rstrip("/")
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("BACKEND_CORS_ORIGINS", "*").split(",")
    if origin.strip()
]

app = FastAPI(title=os.getenv("SERVICE_NAME", "morningstar-api"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthMiddleware)


@app.on_event("startup")
def _startup():
    Base.metadata.create_all(bind=engine)


@app.exception_handler(HTTPException)
def http_exception_handler(_: Request, exc: HTTPException):
    if exc.status_code in {403, 404, 410}:
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": exc.status_code, "detail": exc.detail},
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/")
def root():
    return {"service": "morningstar-api", "message": "OK"}


@app.get("/robots.txt", include_in_schema=False)
def robots():
    body = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /dashboard",
            "Disallow: /control-panel",
            "Disallow: /api/",
            f"Sitemap: {PUBLIC_BASE_URL}/sitemap.xml",
        ]
    )
    return PlainTextResponse(body)


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap():
    body = "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
            "  <url>",
            f"    <loc>{PUBLIC_BASE_URL}/</loc>",
            "    <changefreq>weekly</changefreq>",
            "    <priority>1.0</priority>",
            "  </url>",
            "</urlset>",
        ]
    )
    return Response(content=body, media_type="application/xml")


app.include_router(health_router, prefix="/api/health", tags=["health"])

v1 = APIRouter(prefix="/api/v1", tags=["v1"])
v1.include_router(auth_router)
v1.include_router(file_downloads_router)
v1.include_router(market_router)
v1.include_router(portfolios_router, dependencies=[Depends(require_user)])
v1.include_router(integrations_router, dependencies=[Depends(require_user)])

app.include_router(v1)
