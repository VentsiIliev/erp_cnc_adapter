# 🚀 Quick Start - Installing 32-bit Python

## ⚠️ You Need 32-bit Python!

Your CNC DLL is 32-bit, so you need 32-bit Python. Here's the fastest way to fix this:

---

## 📥 Step 1: Download 32-bit Python

**Click here to download:** 
### [Python 3.11.9 (32-bit) - Direct Download](https://www.python.org/ftp/python/3.11.9/python-3.11.9.exe)

---

## 🔧 Step 2: Install It

1. **Run the downloaded installer** (`python-3.11.9.exe`)

2. **IMPORTANT:** On the first screen:
   - ✅ Check **"Add Python to PATH"**
   - Click **"Customize installation"**

3. **Optional Features:** Check all boxes, click Next

4. **Advanced Options:**
   - ✅ Check **"Install for all users"**
   - 📁 Change install location to: `C:\Python311-32\`
   - Click **Install**

5. Wait for installation to complete

---

## 🎯 Step 3: Setup Your Project (Automated)

**Option A - Run the automated script:**

```powershell
cd "C:\Users\Notebook 1\Desktop\erp_cnc_adapter\erp_cnc_adapter"
.\setup_32bit_venv.ps1
```

This will:
- ✅ Verify 32-bit Python is installed
- ✅ Remove old 64-bit virtual environment
- ✅ Create new 32-bit virtual environment
- ✅ Install all dependencies
- ✅ Verify everything is working

**Option B - Manual setup:**

```powershell
# Navigate to project
cd "C:\Users\Notebook 1\Desktop\erp_cnc_adapter\erp_cnc_adapter"

# Remove old venv
Remove-Item -Recurse -Force .venv

# Create new 32-bit venv
C:\Python311-32\python.exe -m venv .venv

# Activate it
.\.venv\Scripts\Activate.ps1

# Verify it's 32-bit (should print: Python is 32 bit)
python -c "import struct; print('Python is', struct.calcsize('P') * 8, 'bit')"

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

## ▶️ Step 4: Run Your Server

```powershell
.\.venv\Scripts\python.exe .\main.py
```

You should see:
```
2025-01-01 12:00:00 [INFO] src.services.cnc_client: CNC DLL loaded: C:\CNC4.03\cncapi.dll
2025-01-01 12:00:00 [INFO] src.services.cnc_client: CNC connected successfully
INFO:     Uvicorn running on http://127.0.0.1:8002 (Press CTRL+C to quit)
```

---

## ✅ Success!

Your server is now running with 32-bit Python and can communicate with the CNC DLL!

Visit: **http://127.0.0.1:8002/docs** to test the API

---

## ❓ Troubleshooting

### "Setup script won't run"
If PowerShell blocks the script:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### "Python 32-bit not found"
Make sure you installed to exactly: `C:\Python311-32\`

Check if it exists:
```powershell
Test-Path "C:\Python311-32\python.exe"
```

### "Still getting WinError 193"
Your virtual environment is still using 64-bit Python. Delete `.venv` and recreate it:
```powershell
Remove-Item -Recurse -Force .venv
C:\Python311-32\python.exe -m venv .venv
```

---

## 📚 More Help

- Full instructions: See `INSTALL_32BIT_PYTHON.md`
- Support: Check your Python bits with: `python -c "import struct; print(struct.calcsize('P') * 8)"`

