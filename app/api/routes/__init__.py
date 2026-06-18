"""Aggregate all API routers under a single APIRouter."""
from fastapi import APIRouter

from app.api.routes import admin, analysis, auth, dashboard, reports, schedule, watchlist

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(analysis.router)
api_router.include_router(watchlist.router)
api_router.include_router(schedule.router)
api_router.include_router(reports.router)
api_router.include_router(dashboard.router)
api_router.include_router(admin.router)
