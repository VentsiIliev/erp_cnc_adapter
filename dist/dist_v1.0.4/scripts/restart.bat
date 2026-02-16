@echo off
echo Restarting ERP-CNC Adapter...

taskkill /F /IM erp-cnc-adapter.exe >nul 2>&1
timeout /t 2 >nul
schtasks /Run /TN ERPCNCAdapter

echo.
echo Adapter restarted
pause
