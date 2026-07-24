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
    cnc_startup_ready_timeout: int = 60  # seconds to wait for CNC to leave startup states
    auto_start_adapter_on_logon: bool = True
    adapter_startup_delay_seconds: int = 90
    auto_start_cnc_server: bool = True
    auto_start_eding_gui: bool = False
    show_operator_ready_message: bool = True
    job_monitor_poll_interval: float = 1.0  # seconds between job monitor status checks
    jog_pad_pause_hold_interval_ms: int = 500  # milliseconds between jog-pad pause hold requests; 0 disables
    machine_number: str = "CNC1"  # Machine identifier (e.g., CNC1, CNC2, MILL1, etc.)
    task_username: str = ""
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

                if "dll_path" in user_config:
                    self.dll_path = user_config["dll_path"]
                    logger.info("Loaded persisted dll_path: %s", self.dll_path)

                if "ini_path" in user_config:
                    self.ini_path = user_config["ini_path"]
                    logger.info("Loaded persisted ini_path: %s", self.ini_path)

                if "job_done_report_url" in user_config:
                    self.job_done_report_url = user_config["job_done_report_url"]
                    logger.info("Loaded persisted job_done_report_url: %s", self.job_done_report_url)

                if "task_username" in user_config:
                    self.task_username = user_config["task_username"]
                    logger.info("Loaded persisted task_username: %s", self.task_username)

                if "base_dir" in user_config:
                    self.base_dir = user_config["base_dir"]
                    logger.info("Loaded persisted base_dir: %s", self.base_dir)

                if "cnc_retry_interval" in user_config:
                    self.cnc_retry_interval = user_config["cnc_retry_interval"]
                    logger.info("Loaded persisted cnc_retry_interval: %s", self.cnc_retry_interval)

                if "cnc_health_interval" in user_config:
                    self.cnc_health_interval = user_config["cnc_health_interval"]
                    logger.info("Loaded persisted cnc_health_interval: %s", self.cnc_health_interval)

                if "cnc_startup_ready_timeout" in user_config:
                    self.cnc_startup_ready_timeout = user_config["cnc_startup_ready_timeout"]
                    logger.info("Loaded persisted cnc_startup_ready_timeout: %s", self.cnc_startup_ready_timeout)

                if "auto_start_adapter_on_logon" in user_config:
                    self.auto_start_adapter_on_logon = bool(user_config["auto_start_adapter_on_logon"])
                    logger.info("Loaded persisted auto_start_adapter_on_logon: %s", self.auto_start_adapter_on_logon)

                if "adapter_startup_delay_seconds" in user_config:
                    self.adapter_startup_delay_seconds = int(user_config["adapter_startup_delay_seconds"])
                    logger.info("Loaded persisted adapter_startup_delay_seconds: %s", self.adapter_startup_delay_seconds)

                if "auto_start_cnc_server" in user_config:
                    self.auto_start_cnc_server = bool(user_config["auto_start_cnc_server"])
                    logger.info("Loaded persisted auto_start_cnc_server: %s", self.auto_start_cnc_server)

                if "auto_start_eding_gui" in user_config:
                    self.auto_start_eding_gui = bool(user_config["auto_start_eding_gui"])
                    logger.info("Loaded persisted auto_start_eding_gui: %s", self.auto_start_eding_gui)

                if "show_operator_ready_message" in user_config:
                    self.show_operator_ready_message = bool(user_config["show_operator_ready_message"])
                    logger.info("Loaded persisted show_operator_ready_message: %s", self.show_operator_ready_message)

                if "job_monitor_poll_interval" in user_config:
                    self.job_monitor_poll_interval = user_config["job_monitor_poll_interval"]
                    logger.info("Loaded persisted job_monitor_poll_interval: %s", self.job_monitor_poll_interval)

                if "jog_pad_pause_hold_interval_ms" in user_config:
                    self.jog_pad_pause_hold_interval_ms = int(user_config["jog_pad_pause_hold_interval_ms"])
                    logger.info("Loaded persisted jog_pad_pause_hold_interval_ms: %s", self.jog_pad_pause_hold_interval_ms)

                if "port" in user_config:
                    self.port = int(user_config["port"])
                    logger.info("Loaded persisted port: %s", self.port)

                logger.info("Configuration loaded with persisted overrides")
        except Exception as e:
            logger.warning("Could not load persisted config: %s", e)
