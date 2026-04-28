"""
Update the ERP-CNC Adapter EXE

This script stops the adapter, replaces the EXE, and restarts it.
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


def check_adapter_running():
    """Check if the adapter process is running."""
    result = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {EXE_NAME}"],
        capture_output=True,
        text=True
    )
    return EXE_NAME.lower() in result.stdout.lower()


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

    # Step 1: Stop adapter
    print("Step 1: Stopping adapter...")
    run_command(["taskkill", "/F", "/IM", EXE_NAME], "Stopping adapter process")
    time.sleep(2)

    # Step 2: Backup current EXE
    print("\nStep 2: Backing up current EXE...")
    try:
        if os.path.exists(CURRENT_EXE):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            timestamped_backup = f"{BACKUP_EXE}.{timestamp}"
            shutil.copy2(CURRENT_EXE, BACKUP_EXE)
            shutil.copy2(CURRENT_EXE, timestamped_backup)
            print(f"  Backup created: {BACKUP_EXE}")
            print(f"  Timestamped backup: {timestamped_backup}")
        else:
            print("  WARNING: Current EXE not found, skipping backup")
    except Exception as e:
        print(f"  ERROR: Failed to backup: {e}")
        return False

    # Step 3: Replace EXE
    print("\nStep 3: Replacing EXE...")
    try:
        shutil.copy2(new_exe_path, CURRENT_EXE)
        print("  EXE replaced successfully")
    except Exception as e:
        print(f"  ERROR: Failed to replace EXE: {e}")
        return False

    # Step 4: Start adapter
    print("\nStep 4: Starting adapter...")
    if not run_command(["schtasks", "/Run", "/TN", "ERPCNCAdapter"], "Starting adapter"):
        print("  ERROR: Failed to start adapter via scheduled task")
        print("\n  Rolling back to previous version...")

        # Rollback
        if os.path.exists(BACKUP_EXE):
            shutil.copy2(BACKUP_EXE, CURRENT_EXE)
            print("  Rollback complete")
            run_command(["schtasks", "/Run", "/TN", "ERPCNCAdapter"], "Starting adapter with old version")

        return False

    time.sleep(3)

    # Step 5: Verify
    print("\nStep 5: Verifying update...")
    if check_adapter_running():
        print("\n" + "=" * 50)
        print("  UPDATE SUCCESSFUL!")
        print("=" * 50)
        print("\nAdapter is running with the new version.")
        print("URL: http://localhost:8002")
        print(f"\nBackup saved to: {BACKUP_EXE}")
        return True
    else:
        print("\n" + "=" * 50)
        print("  UPDATE FAILED!")
        print("=" * 50)
        print("\nAdapter is not running. Check logs\\adapter.log for details.")
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
