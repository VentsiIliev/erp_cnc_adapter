from dataclasses import dataclass


@dataclass
class Settings:
    dll_path: str = r"C:\CNC4.03\cncapi.dll"
    ini_path: str = r"C:\CNC4.03\cnc.ini"
    host: str = "0.0.0.0"
    port: int = 8002
    log_level: str = "DEBUG"
    cnc_retry_interval: int = 5   # seconds between connection retries
    cnc_health_interval: int = 10  # seconds between heartbeat checks
