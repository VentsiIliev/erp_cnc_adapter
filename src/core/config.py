from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Settings:
    dll_path: str = r"C:\CNC4.03\cncapi.dll"
    ini_path: str = r"C:\CNC4.03\cnc.ini"
    host: str = "0.0.0.0"
    port: int = 8002
    log_level: str = "DEBUG"
    cnc_retry_interval: int = 5   # seconds between connection retries
    cnc_health_interval: int = 10  # seconds between heartbeat checks
    job_monitor_poll_interval: float = 1.0  # seconds between job monitor status checks
    machine_number: str = "CNC1"  # Machine identifier (e.g., CNC1, CNC2, MILL1, etc.)
    # job_done_report_url: str = "http://localhost:8002/actions/cnc_job_done.php"  # Local testing
    job_done_report_url: str = "https://pl.skycode.com/actions/cnc_job_done.php"  # Production URL (HTTPS)
    dev_mode: bool = False
    base_dir: str = r"\\192.168.2.11\Production\CNC\Mills"  # Base directory for job files
    # base_dir: str=r"C:\Users\Notebook 1\Desktop\mills_test_folder" # For testing

    def __post_init__(self):
        """Load persisted configuration overrides after initialization."""
        try:
            from src.core.config_persistence import load_user_config
            user_config = load_user_config()

            if user_config:
                # Apply persisted configuration overrides
                if "machine_number" in user_config:
                    self.machine_number = user_config["machine_number"]
                    logger.info("Loaded persisted machine_number: %s", self.machine_number)

                if "job_done_report_url" in user_config:
                    self.job_done_report_url = user_config["job_done_report_url"]
                    logger.info("Loaded persisted job_done_report_url: %s", self.job_done_report_url)

                if "base_dir" in user_config:
                    self.base_dir = user_config["base_dir"]
                    logger.info("Loaded persisted base_dir: %s", self.base_dir)

                if "cnc_retry_interval" in user_config:
                    self.cnc_retry_interval = user_config["cnc_retry_interval"]
                    logger.info("Loaded persisted cnc_retry_interval: %s", self.cnc_retry_interval)

                if "cnc_health_interval" in user_config:
                    self.cnc_health_interval = user_config["cnc_health_interval"]
                    logger.info("Loaded persisted cnc_health_interval: %s", self.cnc_health_interval)

                if "job_monitor_poll_interval" in user_config:
                    self.job_monitor_poll_interval = user_config["job_monitor_poll_interval"]
                    logger.info("Loaded persisted job_monitor_poll_interval: %s", self.job_monitor_poll_interval)

                logger.info("Configuration loaded with persisted overrides")
        except Exception as e:
            logger.warning("Could not load persisted config: %s", e)
