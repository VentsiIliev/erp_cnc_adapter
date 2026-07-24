import logging
import signal
import socket
import sys

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

    import uvicorn

    from src.app import create_app
    from src.core.config import Settings

    dev_mode = False
    settings = Settings(dev_mode=dev_mode)
    app = create_app(settings)

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

    uvicorn.run(app, host=settings.host, port=settings.port)


def _run_jog_pad() -> int:
    from src.jog_pad.jog_pad import main as jog_pad_main

    return jog_pad_main()


if __name__ == "__main__":
    if "--jog-pad" in sys.argv:
        sys.argv.remove("--jog-pad")
        raise SystemExit(_run_jog_pad())

    _run_adapter()
