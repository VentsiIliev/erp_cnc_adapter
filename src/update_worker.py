"""
Detached update worker script.

Spawned by the /api/update endpoint as a detached process.
Survives the service stop and handles the EXE swap + restart.

Usage:
    python update_worker.py --exe-path <path> --staged-path <path> --service-name ERPCNCAdapter
"""

import argparse
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime

# Note: LOG_DIR will be set after parsing arguments to use the correct installation directory
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("update_worker")


def check_installation_type(service_name: str) -> str:
    """
    Check if the adapter is installed as a Windows Service or Scheduled Task.
    Returns: 'service', 'task', or 'unknown'
    """
    # Check for Windows Service
    result = subprocess.run(
        ["sc", "query", service_name],
        capture_output=True,
        text=True,
        timeout=10
    )
    if result.returncode == 0:
        return "service"

    # Check for Scheduled Task
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", service_name],
        capture_output=True,
        text=True,
        timeout=10
    )
    if result.returncode == 0:
        return "task"

    return "unknown"


def stop_adapter(service_name: str, exe_name: str, install_type: str) -> bool:
    """Stop the adapter (service or task)."""
    if install_type == "service":
        logger.info("  → Detected: Windows Service installation")
        logger.info("  → Stopping service '%s'...", service_name)
        cmd = ["net", "stop", service_name]
        logger.info("Running: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        logger.info("stdout: %s", result.stdout.strip())
        if result.returncode != 0:
            logger.warning("stderr: %s", result.stderr.strip())
            logger.warning("  → Service stop returned an error (may not have been running)")
        else:
            logger.info("  → Service stopped successfully")
        return True

    elif install_type == "task":
        logger.info("  → Detected: Scheduled Task installation")
        logger.info("  → Task name: %s", service_name)
        logger.info("  → No need to stop task (just kill process)")
        # For scheduled tasks, we just kill the process
        return True

    else:
        logger.warning("  → Unknown installation type, will attempt to kill process")
        return True


def start_adapter(service_name: str, install_type: str) -> bool:
    """Start the adapter (service or task)."""
    if install_type == "service":
        logger.info("  → Starting Windows Service '%s'...", service_name)
        cmd = ["net", "start", service_name]
        logger.info("Running: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        logger.info("stdout: %s", result.stdout.strip())
        if result.returncode != 0:
            logger.warning("stderr: %s", result.stderr.strip())
            return False
        logger.info("  → Service started successfully")
        return True

    elif install_type == "task":
        logger.info("  → Starting Scheduled Task '%s'...", service_name)
        cmd = ["schtasks", "/Run", "/TN", service_name]
        logger.info("Running: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        logger.info("stdout: %s", result.stdout.strip())
        if result.returncode != 0:
            logger.warning("stderr: %s", result.stderr.strip())
            return False
        logger.info("  → Task started successfully")
        return True

    else:
        logger.error("  → Cannot start: unknown installation type")
        return False


def run_sc(action: str, service_name: str, timeout: int = 30) -> bool:
    """Legacy function - kept for compatibility."""
    cmd = ["net", action, service_name]
    logger.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    logger.info("stdout: %s", result.stdout.strip())
    if result.returncode != 0:
        logger.warning("stderr: %s", result.stderr.strip())
    return result.returncode == 0


def get_exe_version(exe_path: str) -> str:
    """
    Extract version from EXE file.
    Returns version string or 'unknown' if not found.
    """
    try:
        # Try to run the EXE with --version flag (if supported)
        result = subprocess.run(
            [exe_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            # Extract version from output (format: "ERP-CNC Adapter v1.0.0")
            version_line = result.stdout.strip().split('\n')[0]
            if 'v' in version_line:
                return version_line.split('v')[-1].strip()
    except:
        pass

    # Fallback: Check for VERSION.txt in same directory
    version_file = os.path.join(os.path.dirname(exe_path), "VERSION.txt")
    if os.path.exists(version_file):
        try:
            with open(version_file, 'r') as f:
                content = f.read().strip()
                # Extract version number from file
                for line in content.split('\n'):
                    if 'version' in line.lower() or line.replace('.', '').replace('_', '').isdigit():
                        # Extract version pattern like 1.0.0
                        import re
                        match = re.search(r'(\d+\.\d+\.\d+)', line)
                        if match:
                            return match.group(1)
        except:
            pass

    return "unknown"


def find_latest_backup(exe_dir: str, exe_name: str) -> str | None:
    """Return the path to the most recent .bak.* file, or None."""
    # Find all backup files (both old and new format)
    backups = [
        f for f in os.listdir(exe_dir)
        if f.startswith(exe_name) and ".bak." in f
    ]
    if not backups:
        return None
    # Sort by filename (timestamp is at the end, so this works)
    backups.sort(reverse=True)
    return os.path.join(exe_dir, backups[0])


def main() -> None:
    parser = argparse.ArgumentParser(description="ERP-CNC Adapter update worker")
    parser.add_argument("--exe-path", required=True, help="Path to the current EXE")
    parser.add_argument("--staged-path", required=True, help="Path to the staged new EXE")
    parser.add_argument("--service-name", default="ERPCNCAdapter", help="Windows service name")
    args = parser.parse_args()

    exe_path = args.exe_path
    staged_path = args.staged_path
    service_name = args.service_name
    exe_dir = os.path.dirname(exe_path)
    exe_name = os.path.basename(exe_path)

    # Setup logging with correct path (use the EXE directory, not __file__ directory)
    log_dir = os.path.join(exe_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "update.log")

    # Add file handler now that we know the correct path
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(file_handler)

    # Get file sizes for logging
    current_size_mb = round(os.path.getsize(exe_path) / (1024 * 1024), 2) if os.path.exists(exe_path) else 0
    staged_size_mb = round(os.path.getsize(staged_path) / (1024 * 1024), 2) if os.path.exists(staged_path) else 0

    logger.info("=" * 70)
    logger.info("ERP-CNC ADAPTER UPDATE PROCESS STARTED")
    logger.info("=" * 70)
    logger.info("Configuration:")
    logger.info("  Service name:        %s", service_name)
    logger.info("  Current EXE:         %s", exe_path)
    logger.info("  Current EXE size:    %.2f MB", current_size_mb)
    logger.info("  New EXE (staged):    %s", staged_path)
    logger.info("  New EXE size:        %.2f MB", staged_size_mb)
    logger.info("  Log file:            %s", log_file)
    logger.info("  Update time:         %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # Detect installation type
    install_type = check_installation_type(service_name)
    logger.info("  Installation type:   %s", install_type.upper())
    logger.info("=" * 70)

    # Stop the adapter
    logger.info("")
    logger.info("PHASE 1: Stopping current adapter")
    logger.info("-" * 70)
    stop_adapter(service_name, exe_name, install_type)

    # Give the process time to fully terminate and release file handles
    logger.info("  → Waiting 5 seconds for service to fully terminate...")
    time.sleep(5)

    # Kill any lingering processes that might be locking the file
    logger.info("  → Checking for lingering adapter processes...")
    try:
        result = subprocess.run(
            ["taskkill", "/F", "/IM", exe_name],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            logger.info("  → Killed lingering process(es), waiting 2 seconds for cleanup...")
            time.sleep(2)  # Wait for process cleanup
        else:
            logger.info("  → No lingering processes found")
        logger.info("  Status:      ✓ Service stopped successfully, file handles released")
    except Exception as e:
        logger.warning(f"  → Warning: Could not check for lingering processes: {e}")

    # Backup current EXE
    logger.info("")
    logger.info("PHASE 2: Creating backup and replacing files")

    # Get current version from EXE
    current_version = get_exe_version(exe_path)
    logger.info("  Detected current version: %s", current_version)

    # Create backup filename with version and timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{exe_name}.v{current_version}.bak.{timestamp}"
    backup_path = os.path.join(exe_dir, backup_filename)
    current_size = 0

    if os.path.exists(exe_path):
        current_size = os.path.getsize(exe_path)
        logger.info("-" * 70)
        logger.info("STEP 1: Creating backup")
        logger.info("  Version:     %s", current_version)
        logger.info("  Source:      %s", exe_path)
        logger.info("  Destination: %s", backup_filename)
        logger.info("  Full path:   %s", backup_path)
        logger.info("  Size:        %.2f MB", current_size / (1024 * 1024))
        try:
            shutil.copy2(exe_path, backup_path)
            logger.info("  Status:      ✓ Backup created successfully")
        except Exception as e:
            logger.error("  Status:      ✗ Failed to backup: %s", e)
            logger.error("Aborting update - cannot proceed without backup")
            sys.exit(1)
    else:
        logger.warning("Current EXE not found at %s, skipping backup", exe_path)

    # Replace EXE with staged update (delete + copy instead of move)
    staged_size = os.path.getsize(staged_path) if os.path.exists(staged_path) else 0
    logger.info("-" * 70)
    logger.info("STEP 2: Replacing EXE file")
    logger.info("  Old EXE:     %s (%.2f MB)", exe_path, current_size / (1024 * 1024) if os.path.exists(exe_path) else 0)
    logger.info("  New EXE:     %s (%.2f MB)", staged_path, staged_size / (1024 * 1024))
    try:
        # Try to delete the old EXE first
        if os.path.exists(exe_path):
            logger.info("  → Deleting old EXE...")
            os.remove(exe_path)
            logger.info("  → Old EXE deleted successfully")

        # Copy staged EXE to target location
        logger.info("  → Copying new EXE to target location...")
        shutil.copy2(staged_path, exe_path)
        new_size = os.path.getsize(exe_path)
        logger.info("  → New EXE copied successfully (%.2f MB)", new_size / (1024 * 1024))

        # Clean up staged file
        if os.path.exists(staged_path):
            os.remove(staged_path)
            logger.info("  → Staged file cleaned up")

        logger.info("  Status:      ✓ EXE replacement completed successfully")
    except Exception as e:
        logger.error("  Status:      ✗ Failed to replace EXE: %s", e)
        # Try to restore from backup
        if os.path.exists(backup_path):
            logger.info("-" * 70)
            logger.info("ROLLBACK: Restoring from backup...")
            try:
                shutil.copy2(backup_path, exe_path)
                logger.info("  Status:      ✓ Backup restored successfully")
            except Exception as restore_err:
                logger.error("  Status:      ✗ CRITICAL: Failed to restore backup: %s", restore_err)
        sys.exit(1)

    # Start the adapter
    logger.info("-" * 70)
    logger.info("STEP 3: Restarting adapter")
    logger.info("  Name:        %s", service_name)
    logger.info("  Type:        %s", install_type.upper())
    if start_adapter(service_name, install_type):
        logger.info("  Status:      ✓ Adapter started successfully")
        logger.info("=" * 70)
        logger.info("UPDATE COMPLETED SUCCESSFULLY")
        logger.info("=" * 70)
        logger.info("Summary:")
        logger.info("  • Backup created:    %s", os.path.basename(backup_path))
        logger.info("  • Old EXE size:      %.2f MB", current_size / (1024 * 1024))
        logger.info("  • New EXE size:      %.2f MB", staged_size / (1024 * 1024))
        logger.info("  • Service status:    Running")
        logger.info("  • Completion time:   %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        logger.info("=" * 70)
        logger.info("Update worker finished successfully")
    else:
        logger.error("  Status:      ✗ Failed to start service with new EXE")
        logger.info("=" * 70)
        logger.info("AUTOMATIC ROLLBACK INITIATED")
        logger.info("=" * 70)

        # Rollback
        latest_backup = find_latest_backup(exe_dir, exe_name)
        if latest_backup:
            logger.info("  Rolling back to: %s", os.path.basename(latest_backup))
            try:
                shutil.copy2(latest_backup, exe_path)
                logger.info("  Backup restored, attempting to start adapter...")
                if start_adapter(service_name, install_type):
                    logger.info("  Status:      ✓ Rollback successful, adapter running with previous version")
                else:
                    logger.error("  Status:      ✗ CRITICAL: Rollback failed to start adapter!")
            except Exception as e:
                logger.error("  Status:      ✗ CRITICAL: Rollback copy failed: %s", e)
        else:
            logger.error("  Status:      ✗ No backup found for rollback!")
        logger.info("=" * 70)
        sys.exit(1)



if __name__ == "__main__":
    main()
