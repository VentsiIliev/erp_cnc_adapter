"""
Update the ERP-CNC Adapter EXE

This script stops the service, replaces the EXE, and restarts the service.
Includes automatic rollback on failure.

Usage: python update_adapter.py <path-to-new-exe>
"""

import sys
import os
import subprocess
import time
import shutil
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Find EXE location (distribution vs development mode)
EXE_NAME = "erp-cnc-adapter.exe"
if os.path.exists(os.path.join(PROJECT_ROOT, EXE_NAME)):
    # Distribution mode - EXE is in parent directory
    CURRENT_EXE = os.path.join(PROJECT_ROOT, EXE_NAME)
    BACKUP_EXE = os.path.join(PROJECT_ROOT, "erp-cnc-adapter.exe.backup")
else:
    # Development mode - EXE is in dist/ folder
    CURRENT_EXE = os.path.join(PROJECT_ROOT, "dist", EXE_NAME)
    BACKUP_EXE = os.path.join(PROJECT_ROOT, "dist", "erp-cnc-adapter.exe.backup")


def run_command(cmd, description):
    """Run a command and return success status."""
    print(f"  {description}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def check_service_status():
    """Check if service is running."""
    result = subprocess.run(
        ["sc", "query", "ERPCNCAdapter"],
        capture_output=True,
        text=True
    )
    return "RUNNING" in result.stdout


def update_adapter(new_exe_path):
    """Update the adapter EXE."""
    print("\n" + "=" * 50)
    print("  ERP-CNC Adapter Update")
    print("=" * 50 + "\n")

    # Validate new EXE
    if not os.path.exists(new_exe_path):
        print(f"ERROR: File not found: {new_exe_path}")
        return False

    if not new_exe_path.endswith(".exe"):
        print("ERROR: File must be a .exe file")
        return False

    print(f"New EXE: {new_exe_path}")
    print(f"Current EXE: {CURRENT_EXE}\n")

    # Step 1: Stop service
    print("Step 1: Stopping service...")
    if not run_command(["net", "stop", "ERPCNCAdapter"], "Stopping service"):
        print("  WARNING: Service may not have been running")
    time.sleep(2)

    # Step 2: Backup current EXE
    print("\nStep 2: Backing up current EXE...")
    try:
        if os.path.exists(CURRENT_EXE):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            timestamped_backup = f"{BACKUP_EXE}.{timestamp}"
            shutil.copy2(CURRENT_EXE, BACKUP_EXE)
            shutil.copy2(CURRENT_EXE, timestamped_backup)
            print(f"  ✓ Backup created: {BACKUP_EXE}")
            print(f"  ✓ Timestamped backup: {timestamped_backup}")
        else:
            print("  WARNING: Current EXE not found, skipping backup")
    except Exception as e:
        print(f"  ERROR: Failed to backup: {e}")
        return False

    # Step 3: Replace EXE
    print("\nStep 3: Replacing EXE...")
    try:
        shutil.copy2(new_exe_path, CURRENT_EXE)
        print(f"  ✓ EXE replaced successfully")
    except Exception as e:
        print(f"  ERROR: Failed to replace EXE: {e}")
        return False

    # Step 4: Start service
    print("\nStep 4: Starting service...")
    if not run_command(["net", "start", "ERPCNCAdapter"], "Starting service"):
        print("  ERROR: Failed to start service")
        print("\n  Rolling back to previous version...")

        # Rollback
        if os.path.exists(BACKUP_EXE):
            shutil.copy2(BACKUP_EXE, CURRENT_EXE)
            print("  ✓ Rollback complete")
            run_command(["net", "start", "ERPCNCAdapter"], "Starting service with old version")

        return False

    time.sleep(3)

    # Step 5: Verify
    print("\nStep 5: Verifying update...")
    if check_service_status():
        print("\n" + "=" * 50)
        print("  ✓ UPDATE SUCCESSFUL!")
        print("=" * 50)
        print("\nService is running with the new version.")
        print("URL: http://localhost:8000")
        print(f"\nBackup saved to: {BACKUP_EXE}")
        return True
    else:
        print("\n" + "=" * 50)
        print("  ✗ UPDATE FAILED!")
        print("=" * 50)
        print("\nService is not running. Check logs\\service.log for details.")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python update_adapter.py <path-to-new-exe>")
        print("\nExample:")
        print("  python update_adapter.py C:\\Downloads\\erp-cnc-adapter-v2.exe")
        sys.exit(1)

    new_exe = sys.argv[1]
    success = update_adapter(new_exe)

    print()
    input("Press Enter to exit...")
    sys.exit(0 if success else 1)

