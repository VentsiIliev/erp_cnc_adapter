================================================================
 ERP-CNC Adapter v1.0.1 - Distribution Package
================================================================

QUICK START:
  1. Run the GUI installer EXE, or:
  2. Right-click: scripts\install.bat
  3. Select: "Run as administrator"
  4. Access: http://localhost:8002

CONTENTS:
  erp-cnc-adapter.exe    - The application
  scripts\               - Installation and management scripts
  logs\                  - Log directory (auto-populated)
  VERSION.txt            - Build information

MANAGEMENT:
  Start:     schtasks /Run /TN "ERPCNCAdapter"
  Stop:      taskkill /F /IM erp-cnc-adapter.exe
  Status:    scripts\status.bat
  Restart:   scripts\restart.bat
  Uninstall: scripts\uninstall.bat

For detailed instructions, see scripts\README.md

================================================================
