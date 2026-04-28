"""Helpers for the adapter's no-op CNC placeholder job."""

import sys
from pathlib import Path


PLACEHOLDER_JOB_FILENAME = "no_job_loaded.cnc"


def get_placeholder_job_path() -> Path:
    """Return the no-op job path used to simulate an unloaded CNC job."""
    candidates = []

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / "resources" / PLACEHOLDER_JOB_FILENAME)
        candidates.append(Path(getattr(sys, "_MEIPASS", exe_dir)) / "resources" / PLACEHOLDER_JOB_FILENAME)
    else:
        candidates.append(Path(__file__).resolve().parent.parent.parent / "resources" / PLACEHOLDER_JOB_FILENAME)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    checked = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(f"Placeholder CNC job not found. Checked: {checked}")


def is_placeholder_job(file_name: str | None) -> bool:
    """Return True when a CNC job path points at the adapter placeholder."""
    if not file_name:
        return False
    return Path(file_name).name.lower() == PLACEHOLDER_JOB_FILENAME.lower()