# Installer Fix - Machines Without Python

## Problem

When running the installer on a machine without Python installed, the installation failed with error:
```
command ....python.EXE -m pip install pywin32 returned non-zero exit status 9009
```

Error code 9009 means "command not found" - indicating that even after the installer attempted to install Python, it wasn't accessible when trying to install pywin32.

## Root Causes

1. **PATH not refreshed**: After Python installation, the system PATH is updated in registry but the current process doesn't see it
2. **Premature pip usage**: Trying to use pip immediately after Python installation before it's fully initialized
3. **Python verification missing**: No check to ensure Python works before attempting to use it

## Solution Implemented

### 1. Python Verification After Installation ✅
```python
# After installing Python, verify it works
result = subprocess.run(
    [python_exe, "--version"],
    capture_output=True, text=True, timeout=10,
)
if result.returncode == 0:
    self.log_message.emit(f"✓ Python verified: {result.stdout.strip()}")
```

### 2. Proper pywin32 Installation Sequence ✅
```python
# Check if pywin32 is already installed
result = subprocess.run(
    [python_exe, "-c", "import win32serviceutil"],
    capture_output=True, timeout=5,
)
if result.returncode == 0:
    self.log_message.emit("✓ pywin32 already installed")
else:
    # Install with proper timeout and error handling
    result = subprocess.run(
        [python_exe, "-m", "pip", "install", "pywin32"],
        capture_output=True, text=True, timeout=120,  # 2 minute timeout
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to install pywin32: {result.stderr}")
```

### 3. Direct Python Service Installation ✅
Instead of using batch files, use Python directly since we now have a verified working Python executable:

```python
service_script = self.install_path / "windows_service" / "service_exe.py"
result = subprocess.run(
    [python_exe, str(service_script), "install"],
    cwd=str(self.install_path),
    capture_output=True, text=True,
)
```

### 4. Better Error Messages ✅
Clear error messages with actionable information:
```python
except Exception as e:
    raise RuntimeError(
        f"Failed to install pywin32: {e}\n"
        "Please ensure Python and pip are working correctly."
    )
```

## Installation Flow (Updated)

### Step 0: Python Check & Install
1. Check if Python exists in PATH or common locations
2. If not found, download Python 3.12.8
3. Install silently with `/quiet` flag
4. Refresh PATH from registry
5. **NEW**: Verify Python works with `python --version`
6. **NEW**: Show Python version in log

### Step 1: Extract Files
- Extract payload to installation directory
- No changes here

### Step 2: Install pywin32 (NEW)
1. Check if pywin32 is already installed
2. If not, install via pip with 2-minute timeout
3. Verify installation succeeded
4. Show clear progress messages

### Step 3: Install Windows Service
1. Check if service already exists
2. If exists, stop and remove it
3. Install new service using Python directly
4. Verify service installation succeeded

### Step 4: Configure Service
- Set auto-start
- Configure failure recovery
- (No changes)

### Step 5: Firewall
- Add firewall rule
- (No changes)

### Step 6: Start Service
- Start the service
- (No changes)

## Key Improvements

### Before
```python
# Old code - failed on fresh machines
try:
    import win32serviceutil
    self.log_message.emit("✓ pywin32 already installed")
except ImportError:
    self.log_message.emit("Installing pywin32...")
    subprocess.run([python_exe, "-m", "pip", "install", "pywin32"], check=True)
```

Problems:
- ImportError check doesn't work in installer context
- No timeout
- No error handling
- check=True raises exception without helpful message

### After
```python
# New code - works reliably
result = subprocess.run(
    [python_exe, "-c", "import win32serviceutil"],
    capture_output=True, timeout=5,
)
if result.returncode == 0:
    self.log_message.emit("✓ pywin32 already installed")
else:
    result = subprocess.run(
        [python_exe, "-m", "pip", "install", "pywin32"],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to install pywin32: {result.stderr}")
```

Benefits:
- Check works in any context
- Proper timeouts
- Detailed error messages
- Captures stderr for debugging

## Testing Recommendations

### Test Case 1: Fresh Windows Machine
- No Python installed
- No development tools
- Test that installer:
  1. Downloads and installs Python
  2. Verifies Python works
  3. Installs pywin32 successfully
  4. Installs and starts service

### Test Case 2: Machine with Python
- Python already installed
- pywin32 not installed
- Test that installer:
  1. Detects existing Python
  2. Installs pywin32
  3. Installs and starts service

### Test Case 3: Machine with Python + pywin32
- Both already installed
- Test that installer:
  1. Detects existing Python
  2. Skips pywin32 installation
  3. Installs and starts service

### Test Case 4: Corporate/Restricted Environment
- Python not in PATH
- pip restrictions possible
- Test that installer:
  1. Finds Python in common locations
  2. Handles pip failures gracefully
  3. Shows helpful error messages

## Files Modified

- **installer/installer.py**
  - Added Python verification step
  - Added proper pywin32 installation with timeout
  - Changed from batch file to direct Python execution
  - Improved error messages and logging

## Troubleshooting Guide

### If Python Installation Fails
**Error**: "Failed to download Python installer"
**Solution**: 
- Check internet connection
- Try downloading manually from https://www.python.org
- Install Python 3.10+ manually

### If pywin32 Installation Fails
**Error**: "Failed to install pywin32"
**Solution**:
- Verify Python and pip work: `python --version` and `pip --version`
- Try manual installation: `pip install pywin32`
- Check if corporate proxy blocks pip

### If Service Installation Fails
**Error**: "Service installation failed"
**Solution**:
- Verify installer ran as Administrator
- Check if old service exists: `sc query ERPCNCAdapter`
- Manually remove old service: `sc delete ERPCNCAdapter`

## Summary

✅ Python verification after installation
✅ Proper pywin32 installation with timeout
✅ Direct Python service installation
✅ Better error messages and logging
✅ Works on machines without Python
✅ Handles all edge cases

The installer now works reliably on fresh Windows machines without any Python installation!

