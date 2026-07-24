from fastapi import APIRouter

from src.api import (
    cnc_start, cnc_stop, health, job_load, job_start, job_status, job_unload,
    update, update_page, test_page, monitor_status, monitor_page,
    config_api, config_page, dashboard_page, logs, cnc_motion, jog_pad_launcher
)


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(job_status.router)
api_router.include_router(job_load.router)
api_router.include_router(job_start.router)
api_router.include_router(job_unload.router)
api_router.include_router(cnc_start.router)
api_router.include_router(cnc_stop.router)
api_router.include_router(cnc_motion.router)
api_router.include_router(update.router)
api_router.include_router(update_page.router)
api_router.include_router(test_page.router)
api_router.include_router(monitor_status.router)
api_router.include_router(monitor_page.router)
api_router.include_router(config_api.router)
api_router.include_router(config_page.router)
api_router.include_router(logs.router)
api_router.include_router(dashboard_page.router)
api_router.include_router(jog_pad_launcher.router)


