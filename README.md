# ERP-CNC Adapter

A REST API service that bridges ERP systems with CNC machines, enabling automated job loading, starting, and status monitoring.

## Features

- **REST API** - FastAPI-based endpoints for CNC control
- **Web UI** - Manual update interface with file upload
- **Auto-start** - Runs on boot via Windows Task Scheduler
- **Auto-update** - Self-updating mechanism with rollback support
- **Connection Management** - Automatic reconnection to CNC server
- **Zero Dependencies** - Python-free installation (self-contained EXE)

## Quick Start

### Installation

1. Download `ERP-CNC-Adapter-Setup-v1.0.6.exe`
2. Right-click → **Run as administrator**
3. Follow the installation wizard
4. Done! Service starts automatically

**Installation time**: ~15 seconds  
**Requirements**: Windows 10/11, Administrator rights

### API Endpoints

```
GET  /health        - Health check & version
POST /cnc/start     - Start CNC server
POST /cnc/stop      - Stop CNC server
POST /job/load      - Load G-code job
POST /job/start     - Start loaded job
GET  /job/status    - Get job status
POST /api/update    - Upload new version
GET  /update        - Manual update page
```

### Example Usage

```bash
# Check health
curl http://localhost:8002/health

# Start CNC
curl -X POST http://localhost:8002/cnc/start

# Load job
curl -X POST http://localhost:8002/job/load \
  -H "Content-Type: application/json" \
  -d '{"file_path": "C:/Jobs/part.nc"}'

# Start job
curl -X POST http://localhost:8002/job/start
```

## Architecture

```
┌─────────────────────────────┐
│  ERP System                 │
│  (REST API Client)          │
└─────────┬───────────────────┘
          │ HTTP
          ↓
┌─────────────────────────────┐
│  ERP-CNC Adapter            │
│  • FastAPI Server           │
│  • Connection Manager       │
│  • Update Worker            │
└─────────┬───────────────────┘
          │ CNC API
          ↓
┌─────────────────────────────┐
│  CNC Machine                │
│  (cncapi.dll)               │
└─────────────────────────────┘
```

## Technology Stack

- **Python 3.11** (32-bit) - Embedded in EXE
- **FastAPI** - REST API framework
- **Uvicorn** - ASGI server
- **Pytest** - Testing framework
- **PyInstaller** - EXE packaging
- **PyQt5** - Installer GUI
- **Inno Setup** - Installer builder

## Development

### Prerequisites

- Python 3.11 (32-bit)
- Git
- Administrator rights (for testing service)

### Setup

```powershell
# Clone repository
git clone https://github.com/VentsiIliev/erp_cnc_adapter.git
cd erp_cnc_adapter

# Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### Run Tests

```powershell
cd util_scripts
.\run_tests.bat
```

### Build EXE

```powershell
cd util_scripts
.\build.bat
```

### Build Installer

```powershell
cd util_scripts
.\build_installer.bat
```

## Project Structure

```
erp_cnc_adapter/
├── cncapi/              # CNC DLL interface
├── src/
│   ├── handlers/        # API endpoint handlers
│   ├── schemas/         # Pydantic models
│   └── services/        # Business logic
├── tests/               # Test suite
├── installer/           # Installer GUI
├── util_scripts/        # Build scripts
├── scripts/             # Installation & management scripts
├── docs/                # Documentation
├── main.py              # Application entry point
├── version.py           # Version info
└── requirements.txt     # Dependencies
```

## Installation Methods

### Method 1: Graphical Installer (Recommended)
- Double-click EXE
- Auto-detects installation type
- Configures everything automatically

### Method 2: Manual (Advanced)
```powershell
# Extract files
xcopy /E /I dist\dist_v1.0.6 "C:\Program Files\ERP-CNC Adapter"

# Create scheduled task
schtasks /Create /TN ERPCNCAdapter \
  /TR "C:\Program Files\ERP-CNC Adapter\erp-cnc-adapter.exe" \
  /SC ONSTART /RU SYSTEM /RL HIGHEST /F

# Configure firewall
netsh advfirewall firewall add rule name="ERP-CNC Adapter" \
  dir=in action=allow protocol=TCP localport=8002

# Start task
schtasks /Run /TN ERPCNCAdapter
```

## Update Process

### Automatic (via API)
```bash
curl -X POST http://localhost:8002/api/update \
  -F "file=@erp-cnc-adapter.exe"
```

### Manual (via Web UI)
1. Open http://localhost:8002/update
2. Select new EXE file
3. Click "Upload and Update"
4. Wait for automatic restart

### What Happens
1. Upload validates new EXE
2. Saves to `staged-update.exe`
3. Spawns update worker
4. Stops current app
5. Backs up current version
6. Replaces EXE
7. Starts new version
8. Verifies startup (rollback if fails)

## Service Management

### Check Status
```powershell
schtasks /Query /TN ERPCNCAdapter
Get-Process erp-cnc-adapter -ErrorAction SilentlyContinue
```

### Start
```powershell
schtasks /Run /TN ERPCNCAdapter
```

### Stop
```powershell
taskkill /F /IM erp-cnc-adapter.exe
```

### Uninstall
```powershell
schtasks /Delete /TN ERPCNCAdapter /F
```

## Logs

- **Application**: `logs/adapter.log`
- **Installation**: `logs/installation.log`
- **Update**: `logs/update.log`
- **Service**: `logs/service.log`

## Troubleshooting

### Service Not Running?
```powershell
# Check logs
type "C:\Program Files\ERP-CNC Adapter\logs\adapter.log"

# Start manually
schtasks /Run /TN ERPCNCAdapter
```

### Port 8002 In Use?
```powershell
netstat -ano | findstr :8002
taskkill /F /PID [PID]
```

### Update Failed?
Check `logs/update.log` for details. The update worker automatically rolls back on failure.

## Version History

- **v1.0.6** - Task Scheduler installation, update worker improvements
- **v1.0.5** - Enhanced update logging with version tracking
- **v1.0.4** - Update mechanism fixes
- **v1.0.3** - Python-free installer
- **v1.0.2** - Initial Windows Service implementation
- **v1.0.1** - Basic API functionality
- **v1.0.0** - Initial release

## License

Proprietary - All rights reserved

## Contributing

This is a private repository. Contact the maintainer for access.

## Support

For issues or questions, open an issue on GitHub or contact the development team.

---

**Built with ❤️ for CNC automation**

