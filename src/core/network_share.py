"""Explicit authentication for configured Windows UNC job shares."""

from dataclasses import dataclass
import logging
import os
import subprocess

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ShareAuthResult:
    attempted: bool
    ok: bool
    share: str
    message: str
    return_code: int | None = None


def unc_share_root(path: str) -> str | None:
    """Return \\server\share for a UNC path, or None for local/invalid paths."""
    normalized = (path or "").replace("/", "\\")
    if not normalized.startswith("\\\\"):
        return None

    parts = [part for part in normalized.strip("\\").split("\\") if part]
    if len(parts) < 2:
        return None
    return f"\\\\{parts[0]}\\{parts[1]}"


def _hidden_startupinfo():
    if os.name != "nt":
        return None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return startupinfo


def _run_net_use(args: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        startupinfo=_hidden_startupinfo(),
    )


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(
        part.strip()
        for part in (result.stdout or "", result.stderr or "")
        if part.strip()
    )


def _is_conflicting_connection(output: str) -> bool:
    lowered = output.lower()
    return "1219" in lowered or "multiple connections" in lowered


def ensure_unc_share_authenticated(
    base_dir: str,
    username: str,
    password: str,
    *,
    timeout: float = 10.0,
) -> ShareAuthResult:
    """Authenticate the configured UNC share with explicit credentials.

    Only the derived \\server\share connection is touched. Passwords are passed
    as argv, never through a shell command string, and are not returned/logged.
    """
    share = unc_share_root(base_dir) or ""
    if not share:
        return ShareAuthResult(False, True, "", "Not a UNC path")
    if not username or not password:
        return ShareAuthResult(False, False, share, "CNC share credentials are not configured")

    command = ["net", "use", share, f"/user:{username}", password, "/persistent:no"]
    try:
        result = _run_net_use(command, timeout)
    except subprocess.TimeoutExpired:
        return ShareAuthResult(True, False, share, "Timed out while authenticating CNC job share")
    except OSError as exc:
        return ShareAuthResult(True, False, share, f"Could not run net use: {exc}")

    output = _combined_output(result)
    if result.returncode == 0:
        return ShareAuthResult(True, True, share, "CNC job share authenticated", result.returncode)

    if _is_conflicting_connection(output):
        logger.warning("Replacing conflicting SMB connection for CNC job share: %s", share)
        try:
            _run_net_use(["net", "use", share, "/delete", "/y"], timeout)
            retry = _run_net_use(command, timeout)
        except subprocess.TimeoutExpired:
            return ShareAuthResult(True, False, share, "Timed out while replacing CNC job share connection")
        except OSError as exc:
            return ShareAuthResult(True, False, share, f"Could not replace CNC job share connection: {exc}")

        retry_output = _combined_output(retry)
        if retry.returncode == 0:
            return ShareAuthResult(True, True, share, "CNC job share authenticated", retry.returncode)
        return ShareAuthResult(
            True,
            False,
            share,
            retry_output or f"net use failed with exit code {retry.returncode}",
            retry.returncode,
        )

    return ShareAuthResult(
        True,
        False,
        share,
        output or f"net use failed with exit code {result.returncode}",
        result.returncode,
    )
