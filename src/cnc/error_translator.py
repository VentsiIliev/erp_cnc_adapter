"""CNC Error Code Translator - Human-readable error messages."""

from typing import Dict, Tuple


class CNCErrorTranslator:
    """Translates CNC API error codes to human-readable messages."""

    # Error code definitions from cncenums.py
    ERROR_CODES: Dict[int, Tuple[str, str, str]] = {
        # Success
        0: ("SUCCESS", "Operation completed successfully", "No action needed"),

        # Informational (not errors)
        1: ("BUFFER_EMPTY", "Command buffer is empty", "System is waiting for commands"),
        2: ("TRACE", "Trace message", "Diagnostic information for debugging"),
        3: ("USER_INFO", "User information", "Informational message"),
        4: ("SHUTDOWN", "System shutting down", "CNC Server is stopping"),
        5: ("EXISTING", "Already exists", "Resource already exists"),
        6: ("ALREADY_RUNNING", "Job already running", "A job is currently executing - cannot load new job or start another job while one is running. Wait for current job to finish or stop it first"),
        7: ("ALREADY_CONNECTED", "Already connected", "Connection already established"),

        # Errors
        8: ("ERROR", "General error", "Check logs for details"),
        9: ("INVALID_PARAMETER", "Invalid parameter", "Check the provided parameters - wrong value, missing required field, or incorrect format"),
        10: ("INVALID_STATE", "Invalid state for operation", "Machine is not in the correct state for this operation - may be running, in error, or not ready. Check current CNC state before retrying"),
        11: ("CONFIG_ERROR", "Configuration error", "Problem with cnc.ini or configuration settings - check configuration files"),
        12: ("INTERNAL_ERROR", "Internal system error", "Critical internal error - may require CNC Server restart"),
        13: ("CONTROL_ENGINE_ERROR", "Control engine error", "Problem with the control engine module"),
        14: ("EXECUTION_ERROR", "Execution error", "Error during command execution - check G-code syntax and operation validity"),
        15: ("CPU_ERROR", "CPU communication error", "Problem communicating with control board - check hardware connections"),
        16: ("MOTION_ERROR", "Motion control error", "Problem with motion system - possible axis jam, lost steps, or servo error"),
        17: ("SYSTEM_ERROR", "System error", "OS-level or hardware error - check system logs"),
        18: ("TIMEOUT", "Operation timeout", "Operation took too long - check network, system load, or operation complexity"),
        19: ("CE_EXECUTION_ERROR", "Control engine execution error", "Error during control engine command execution"),
        20: ("FILE_OPEN_ERROR", "Cannot open file", "File not found, no access rights, network path unavailable, or file locked by another program"),
        21: ("COLLISION_ERROR", "Collision detected", "Potential or actual collision detected - check tool position and trajectory"),
        22: ("SERVER_NOT_RUNNING", "CNC Server not running", "CncServer.exe is not started - start CNC Server using /api/cnc/start"),
        23: ("VERSION_MISMATCH", "DLL/Server version mismatch", "CNCAPI.DLL version doesn't match CncServer.exe - use compatible versions"),
        24: ("NOT_CONNECTED", "Not connected to CNC", "No connection to CNC controller - call Connect() first or check /api/cnc/start"),
        25: ("BUFFER_FULL", "Command buffer full", "Too many pending commands - wait for current commands to finish"),

        # Special codes (undocumented but observed in practice)
        -1: ("BUSY_OR_ERROR", "Operation rejected - machine busy, in error, or drives not enabled", "Enable the drives/motion and clear safety or E-stop conditions. If a job or MDI command is running, wait for it to finish or stop it first. If the machine is idle, check the CNC state/errors or restart CNC Server"),
        -2: ("CONNECTION_FAILED", "Failed to establish connection", "Cannot connect to CNC Server - verify server is running"),
        -17: ("SERVER_NOT_READY", "CNC Server not running or not ready", "CncServer.exe is not running or not fully started. Start CNC Server using /api/cnc/start and wait for it to initialize"),
    }

    @classmethod
    def translate(cls, error_code: int) -> Dict[str, str]:
        """
        Translate error code to human-readable message.

        Args:
            error_code: CNC API error code

        Returns:
            Dictionary with error_code, name, message, and suggestion
        """
        if error_code in cls.ERROR_CODES:
            name, message, suggestion = cls.ERROR_CODES[error_code]
            severity = "success" if error_code == 0 else ("info" if error_code < 8 else "error")
        else:
            name = "UNKNOWN_CODE"
            message = f"Unknown error code: {error_code}"
            suggestion = "This error code is not documented - check CNC documentation"
            severity = "error"

        return {
            "error_code": error_code,
            "name": name,
            "message": message,
            "suggestion": suggestion,
            "severity": severity,
            "is_success": error_code == 0,
        }

    @classmethod
    def format_error(cls, error_code: int, operation: str = "") -> str:
        """
        Format error as human-readable string.

        Args:
            error_code: CNC API error code
            operation: Name of the operation that failed

        Returns:
            Formatted error message
        """
        info = cls.translate(error_code)

        if info["is_success"]:
            return f"{operation} succeeded" if operation else "Success"

        parts = []
        if operation:
            parts.append(f"{operation} failed")
        parts.append(f"[{info['name']}] {info['message']}")
        if info['suggestion']:
            parts.append(f"→ {info['suggestion']}")

        return ": ".join(parts) if operation else " ".join(parts)


# Convenience function
def translate_error(error_code: int) -> Dict[str, str]:
    """Translate CNC error code to human-readable information."""
    return CNCErrorTranslator.translate(error_code)


def format_error(error_code: int, operation: str = "") -> str:
    """Format CNC error as human-readable string."""
    return CNCErrorTranslator.format_error(error_code, operation)

