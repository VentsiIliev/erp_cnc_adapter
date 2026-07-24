"""Smoke tests for README and requirements completeness."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
README = PROJECT_ROOT / "README.md"
REQUIREMENTS = PROJECT_ROOT / "requirements.txt"


def test_readme_covers_setup_build_and_key_endpoints():
    text = README.read_text(encoding="utf-8").lower()

    for phrase in ("environment setup", "build process", "api endpoints"):
        assert phrase in text, f"Missing section: {phrase}"

    expected_endpoints = [
        "/",
        "/api/health",
        "/dashboard",
        "/config",
        "/monitor",
        "/test",
        "/update",
        "/api/cnc/start",
        "/api/cnc/stop",
        "/api/cnc/job/load/{job_number}/{step}/{qty}",
        "/api/cnc/job/start",
        "/api/cnc/job/status",
        "/api/cnc/job/unload",
        "/api/cnc/monitor/status",
        "/api/update",
        "/api/update/rollback",
        "/api/update/backups",
        "/api/config",
        "/api/logs",
        "/actions/cnc_job_done.php",
        "/favicon.ico",
    ]
    for endpoint in expected_endpoints:
        assert endpoint in text, f"README is missing endpoint: {endpoint}"

    expected_params = [
        "job_number",
        "step",
        "qty",
        "lines",
        "file",
        "m",
        "c",
        "s",
        "machine_number",
        "dll_path",
        "ini_path",
        "job_done_report_url",
        "base_dir",
        "run_as_windows_user",
        "task_username",
        "task_password",
        "restart_adapter_task",
        "port",
        "cnc_retry_interval",
        "cnc_health_interval",
        "auto_start_adapter_on_logon",
        "adapter_startup_delay_seconds",
        "job_monitor_poll_interval",
        "jog_pad_pause_hold_interval_ms",
    ]
    for param in expected_params:
        assert param in text, f"README is missing parameter: {param}"


def test_requirements_include_runtime_and_build_dependencies():
    req_text = REQUIREMENTS.read_text(encoding="utf-8").lower()

    expected_packages = [
        "fastapi",
        "uvicorn[standard]",
        "python-multipart",
        "pydantic",
        "pyinstaller",
        "pytest",
        "pytest-timeout",
        "pytest-asyncio",
        "httpx",
        "pyqt5",
    ]
    for package in expected_packages:
        assert package in req_text, f"Missing dependency: {package}"
