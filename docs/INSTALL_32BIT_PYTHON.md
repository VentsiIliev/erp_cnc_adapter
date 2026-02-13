# How to Install 32-bit Python for CNC DLL

## Problem
Your CNC DLL (`cncapi.dll`) is 32-bit, but your current Python is 64-bit. They must match.

**Error:**
```
OSError: [WinError 193] %1 is not a valid Win32 application
```

## Solution: Install 32-bit Python

### Step 1: Download 32-bit Python

1. Go to: https://www.python.org/downloads/windows/
2. Find **Python 3.11.x** or **Python 3.10.x** (recommended for stability)
3. Download the **Windows installer (32-bit)** - look for "x86" NOT "x86-64"
   - Example: `python-3.11.9-webinstall.exe` (32-bit)
   - Or: `python-3.11.9.exe` (32-bit installer)

**Important:** Make sure you download the 32-bit (x86) version!

### Step 2: Install Python 32-bit

1. Run the installer
2. ✅ Check "Add Python to PATH"
3. Choose "Customize installation"
4. Check all optional features
5. **Important:** Set custom install location:
   ```
   C:\Python311-32\
   ```
   (This keeps it separate from your 64-bit Python)
6. Complete the installation

### Step 3: Create New Virtual Environment with 32-bit Python

```powershell
# Remove old 64-bit venv
Remove-Item -Recurse -Force "C:\Users\Notebook 1\Desktop\erp_cnc_adapter\erp_cnc_adapter\.venv"

# Create new 32-bit venv
C:\Python311-32\python.exe -m venv "C:\Users\Notebook 1\Desktop\erp_cnc_adapter\erp_cnc_adapter\.venv"

# Activate it
cd "C:\Users\Notebook 1\Desktop\erp_cnc_adapter\erp_cnc_adapter"
.\.venv\Scripts\Activate.ps1

# Verify it's 32-bit
python -c "import struct; print('Python is', struct.calcsize('P') * 8, 'bit')"
# Should print: Python is 32 bit

# Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Run Your Server

```powershell
.\.venv\Scripts\python.exe .\main.py
```

## Alternative: Quick Install Script

I've created an automated script below. Run it to set everything up automatically.

---

## Direct Download Links (32-bit Python)

- **Python 3.11.9 (32-bit)**: https://www.python.org/ftp/python/3.11.9/python-3.11.9.exe
- **Python 3.10.11 (32-bit)**: https://www.python.org/ftp/python/3.10.11/python-3.10.11.exe

---

## Verify Installation

After installing, verify:

```powershell
C:\Python311-32\python.exe --version
C:\Python311-32\python.exe -c "import struct; print('Python is', struct.calcsize('P') * 8, 'bit')"
```

Should output:
```
Python 3.11.9
Python is 32 bit
```

