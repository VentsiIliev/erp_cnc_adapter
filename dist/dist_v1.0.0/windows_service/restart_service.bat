@echo off
echo Restarting ERP-CNC Adapter Service...

net stop ERPCNCAdapter
timeout /t 2 >nul
net start ERPCNCAdapter

echo.
echo Service restarted
pause

