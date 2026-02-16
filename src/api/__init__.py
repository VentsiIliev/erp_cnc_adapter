from fastapi import APIRouter

from src.api import cnc_start, cnc_stop, health, job_load, job_start, job_status, update, update_page

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(job_status.router)
api_router.include_router(job_load.router)
api_router.include_router(job_start.router)
api_router.include_router(cnc_start.router)
api_router.include_router(cnc_stop.router)
api_router.include_router(update.router)
api_router.include_router(update_page.router)

