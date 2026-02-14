================================================================
 ERP-CNC Adapter v1.0.0 - Distribution Package
================================================================

QUICK START:
  1. Ensure Python 3.8+ (32-bit) is installed on target machine
  2. Right-click: windows_service\install_service.bat
  3. Select: "Run as administrator"
  4. Access: http://localhost:8000

CONTENTS:
  erp-cnc-adapter.exe    - The application
  windows_service\       - Service installation and management
  logs\                  - Log directory (auto-populated)
  VERSION.txt            - Build information

DOCUMENTATION:
  windows_service\README.md - Complete service documentation

MANAGEMENT:
  Start:     net start ERPCNCAdapter
  Stop:      net stop ERPCNCAdapter
  Status:    windows_service\service_status.bat
  Uninstall: windows_service\uninstall_service.bat

UPDATING:
  python windows_service\update_adapter.py path\to\new-exe

For detailed instructions, see windows_service\README.md

================================================================
