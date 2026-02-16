import logging
import signal
import socket
import sys

import uvicorn

from src.app import create_app
from src.core.config import Settings

logger = logging.getLogger(__name__)

dev_mode = False
settings = Settings(dev_mode=dev_mode)
app = create_app(settings)


def signal_handler(sig, frame):
    """Handle shutdown signals (Ctrl+C, etc.) to ensure clean disconnect."""
    logger.info("Shutdown signal received, cleaning up...")
    services = getattr(app.state, "services", None)
    if services is not None:
        services.cnc_client.disconnect()
    logger.info("Cleanup complete, exiting")
    sys.exit(0)


if __name__ == "__main__":
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
