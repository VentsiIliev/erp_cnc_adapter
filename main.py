import logging
import signal
import socket
import sys
import time

logger = logging.getLogger(__name__)
app = None
settings = None


def signal_handler(sig, frame):
    """Handle shutdown signals (Ctrl+C, etc.) to ensure clean disconnect."""
    logger.info("Shutdown signal received, cleaning up...")
    if app is not None:
        services = getattr(app.state, "services", None)
        if services is not None:
            services.cnc_client.disconnect()
    logger.info("Cleanup complete, exiting")
    sys.exit(0)


def _run_adapter() -> None:
    global app, settings

    process_start = time.perf_counter()

    import uvicorn

    from src.app import create_app
    from src.core.config import Settings

    dev_mode = False
    settings_start = time.perf_counter()
    settings = Settings(dev_mode=dev_mode)
    settings_elapsed_ms = (time.perf_counter() - settings_start) * 1000

    app_start = time.perf_counter()
    app = create_app(settings)
    app_elapsed_ms = (time.perf_counter() - app_start) * 1000

    logger.info("Startup timing: Settings loaded in %.1fms", settings_elapsed_ms)
    logger.info("Startup timing: FastAPI app created in %.1fms", app_elapsed_ms)
    logger.info(
        "Startup context: frozen=%s executable=%s argv=%s",
        getattr(sys, "frozen", False),
        sys.executable,
        sys.argv,
    )
    logger.info("Startup timing: process entry to app ready %.1fms", (time.perf_counter() - process_start) * 1000)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        local_ip = "unknown"

    logger.info("Starting ERP-CNC Adapter on %s:%d", settings.host, settings.port)
    logger.info("  Local:   http://127.0.0.1:%d", settings.port)
    logger.info("  Network: http://%s:%d", local_ip, settings.port)
    logger.info("Startup timing: handing off to uvicorn at %.1fms", (time.perf_counter() - process_start) * 1000)

    uvicorn.run(app, host=settings.host, port=settings.port)


def _run_update_worker() -> int:
    from src.update_worker import main as update_worker_main

    update_worker_main()
    return 0


def _run_jog_pad() -> int:
    from src.jog_pad.jog_pad import main as jog_pad_main

    return jog_pad_main()


if __name__ == "__main__":
    if "--update-worker" in sys.argv:
        sys.argv.remove("--update-worker")
        raise SystemExit(_run_update_worker())

    if "--jog-pad" in sys.argv:
        sys.argv.remove("--jog-pad")
        raise SystemExit(_run_jog_pad())

    _run_adapter()
