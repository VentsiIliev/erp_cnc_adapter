# Version-Aware Backup Naming - Update

## Overview

Backup files now include the version number of the EXE being backed up, making it easier to identify which version each backup contains.

## New Backup Naming Format

### Before
```
erp-cnc-adapter.exe.bak.20260213_160042
```

### After
```
erp-cnc-adapter.exe.v1.0.0.bak.20260213_160042
```

## Format Structure

```
<exe-name>.v<version>.bak.<timestamp>
```

Where:
- **exe-name**: The original EXE filename (e.g., `erp-cnc-adapter.exe`)
- **version**: The version number extracted from the EXE (e.g., `1.0.0`)
- **timestamp**: Date and time of backup (e.g., `20260213_160042`)

## Version Detection

The system attempts to extract the version using multiple methods:

### Method 1: VERSION.txt File
Looks for a `VERSION.txt` file in the same directory as the EXE and extracts version pattern (e.g., `1.0.0`)

### Method 2: Fallback
If version cannot be detected, uses `unknown` as the version:
```
erp-cnc-adapter.exe.vunknown.bak.20260213_160042
```

## Examples

### Backup from v1.0.0
```
erp-cnc-adapter.exe.v1.0.0.bak.20260213_160042
```

### Backup from v2.5.3
```
erp-cnc-adapter.exe.v2.5.3.bak.20260213_165430
```

### Backup from version 1.2.0-beta
```
erp-cnc-adapter.exe.v1.2.0.bak.20260213_170105
```

## Enhanced Logging

The update log now shows the detected version during backup creation:

```
PHASE 2: Creating backup and replacing files
  Detected current version: 1.0.0
----------------------------------------------------------------------
STEP 1: Creating backup
  Version:     1.0.0
  Source:      C:\...\test_install\erp-cnc-adapter.exe
  Destination: erp-cnc-adapter.exe.v1.0.0.bak.20260213_160042
  Full path:   C:\...\test_install\erp-cnc-adapter.exe.v1.0.0.bak.20260213_160042
  Size:        11.48 MB
  Status:      ✓ Backup created successfully
```

## Backward Compatibility

The system is fully backward compatible with old backup format:

### Listing Backups
Both formats are recognized and listed:
```
- erp-cnc-adapter.exe.v1.0.5.bak.20260213_165430  (11.48 MB)  ← New format
- erp-cnc-adapter.exe.v1.0.0.bak.20260213_160042  (11.48 MB)  ← New format
- erp-cnc-adapter.exe.bak.20260213_155620         (11.48 MB)  ← Old format
```

### Rollback
Rollback works with both formats - the system automatically finds the most recent backup regardless of naming format.

### Rotation
Backup rotation (keeping max 5 backups) works with both formats.

## Benefits

### 1. Easy Version Identification ✅
Quickly see which version each backup contains without needing to check logs or restore it.

### 2. Audit Trail ✅
Clear history of which versions were installed:
```
erp-cnc-adapter.exe.v1.0.5.bak.20260213_170000  ← Upgraded to 1.0.6
erp-cnc-adapter.exe.v1.0.4.bak.20260213_165000  ← Upgraded to 1.0.5
erp-cnc-adapter.exe.v1.0.3.bak.20260213_164000  ← Upgraded to 1.0.4
```

### 3. Selective Rollback ✅
Easily identify which backup to restore to get back to a specific version.

### 4. Troubleshooting ✅
When issues occur, immediately know which version was running when the problem started.

### 5. Change Tracking ✅
See the progression of versions over time:
- `v1.0.0` → `v1.0.3` → `v1.0.5` → `v1.0.10`

## Update Page Display

The `/update` page shows backups with their full names, making version identification immediate:

```
Available Backups:
┌──────────────────────────────────────────────────────────┬──────────┬───────────────────┐
│ Filename                                                  │ Size     │ Date              │
├──────────────────────────────────────────────────────────┼──────────┼───────────────────┤
│ erp-cnc-adapter.exe.v1.0.5.bak.20260213_165430           │ 11.48 MB │ 2026-02-13 16:54  │
│ erp-cnc-adapter.exe.v1.0.0.bak.20260213_160042           │ 11.48 MB │ 2026-02-13 16:00  │
└──────────────────────────────────────────────────────────┴──────────┴───────────────────┘
```

## Technical Implementation

### Version Extraction (update_worker.py)
```python
def get_exe_version(exe_path: str) -> str:
    """Extract version from EXE file."""
    # Check VERSION.txt in same directory
    version_file = os.path.join(os.path.dirname(exe_path), "VERSION.txt")
    if os.path.exists(version_file):
        # Extract version pattern (e.g., 1.0.0)
        match = re.search(r'(\d+\.\d+\.\d+)', content)
        if match:
            return match.group(1)
    return "unknown"
```

### Backup Creation
```python
# Get current version
current_version = get_exe_version(exe_path)

# Create backup with version
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_filename = f"{exe_name}.v{current_version}.bak.{timestamp}"
```

### Backup Listing (handlers/update.py)
```python
def _list_backups() -> list[BackupInfo]:
    """List backup files sorted newest-first."""
    # Match both old and new formats
    if ".bak." in f and f.startswith(EXE_NAME):
        # Extract timestamp (last part after .bak.)
        parts = f.split(".bak.")
        if len(parts) == 2:
            backups.append(BackupInfo(...))
```

## Migration Notes

### Existing Installations
- Old backups (without version) continue to work
- New backups automatically include version
- No manual migration needed
- Both formats coexist seamlessly

### Future Versions
All future backups will include the version number, making it progressively easier to track version history.

## Example Scenario

### Initial Install (v1.0.0)
No backups yet

### Update to v1.0.5
Creates: `erp-cnc-adapter.exe.v1.0.0.bak.20260213_160000`

### Update to v1.0.10
Creates: `erp-cnc-adapter.exe.v1.0.5.bak.20260213_170000`

### Update to v2.0.0
Creates: `erp-cnc-adapter.exe.v1.0.10.bak.20260213_180000`

### Rollback to v1.0.5
- Select backup: `erp-cnc-adapter.exe.v1.0.5.bak.20260213_170000`
- System restores version 1.0.5
- Creates new backup of v2.0.0 before rollback

## Summary

✅ Version included in backup filename
✅ Backward compatible with old format  
✅ Automatic version detection
✅ Enhanced logging shows version
✅ Easy version identification
✅ Better audit trail
✅ No manual changes required

The backup system now provides clear version tracking while maintaining full compatibility with existing backups!

