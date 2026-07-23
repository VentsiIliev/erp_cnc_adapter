# Machine Health Dashboard

Standalone dashboard for checking multiple ERP-CNC Adapter instances from one page.

This is intentionally separate from the ERP-CNC Adapter runtime. It is not copied into adapter distribution folders and is not packaged into the adapter installer.

## Run

```powershell
cd "C:\Users\Notebook 1\Desktop\github_repos\erp_cnc_adapter"
python .\machine_health_dashboard\server.py
```

Or double-click:

```text
machine_health_dashboard\start_dashboard.bat
```

Open:

```text
http://127.0.0.1:8010
```

The dashboard polls each configured machine's `/api/health` endpoint server-side every 10 seconds. Click a machine card to open that machine's own adapter dashboard.

## Configuration

Edit `machines.json` to add or remove machines.

Current machines:

- CNC1: `192.168.13.83:8002`
- CNC3: `192.168.13.88:8002`
- CNC4: `192.168.13.89:8002`
- CNC5: `192.168.13.86:8002`
- CNC6: `192.168.13.87:8002`
- CNC7: `192.168.13.85:8002`
