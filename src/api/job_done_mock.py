
"""Mock endpoint for testing job done reports."""

import logging
from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()


# Store recent reports for testing
recent_reports = []


@router.get("/actions/cnc_job_done.php")
async def job_done_report(
    request: Request,
    m: str = Query(..., description="Machine number (e.g., cnc1)"),
    c: str = Query(..., description="Job number (12 digits)"),
    s: str = Query(..., description="Step number"),
):
    """
    Mock endpoint to receive job done reports.

    In production, this would be: http://pl.skycode.com/actions/cnc_job_done.php
    For testing, it runs locally and logs the reports.

    Parameters:
    - m: machine number (e.g., cnc1, cnc2)
    - c: job number (12-digit code)
    - s: step number
    """
    timestamp = datetime.now().isoformat()

    report = {
        "timestamp": timestamp,
        "machine": m,
        "job_number": c,
        "step": s,
    }

    # Store report
    recent_reports.append(report)
    if len(recent_reports) > 100:
        recent_reports.pop(0)  # Keep only last 100 reports

    # Log the report
    logger.info("=" * 80)
    logger.info("JOB DONE REPORT RECEIVED")
    logger.info("=" * 80)
    logger.info("Timestamp: %s", timestamp)
    logger.info("Machine: %s", m)
    logger.info("Job Number: %s", c)
    logger.info("Step: %s", s)
    logger.info("=" * 80)

    # Get request details
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    full_url = str(request.url)

    # Build history table
    if not recent_reports:
        history_rows = '<tr><td colspan="4" style="text-align: center; color: #888; padding: 20px;">No reports yet</td></tr>'
    else:
        history_rows = ""
        for r in reversed(recent_reports[-20:]):  # Last 20, newest first
            ts = datetime.fromisoformat(r["timestamp"])
            time_str = ts.strftime("%Y-%m-%d %H:%M:%S")
            # Highlight current report
            highlight = ' style="background: #f0f9ff;"' if r == report else ''
            history_rows += f"""
                <tr{highlight}>
                    <td>{time_str}</td>
                    <td>{r["machine"]}</td>
                    <td>{r["job_number"]}</td>
                    <td>{r["step"]}</td>
                </tr>
            """

    # Return simple HTML page
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Job Done Report</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #f5f5f5;
                padding: 20px;
            }}
            
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 8px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                padding: 30px;
            }}
            
            h1 {{
                color: #333;
                font-size: 24px;
                margin-bottom: 5px;
                font-weight: 600;
            }}
            
            .subtitle {{
                color: #666;
                margin-bottom: 25px;
                font-size: 14px;
            }}
            
            .section {{
                margin-bottom: 30px;
            }}
            
            .section-title {{
                font-weight: 600;
                color: #333;
                margin-bottom: 12px;
                font-size: 16px;
                border-bottom: 2px solid #e5e5e5;
                padding-bottom: 8px;
            }}
            
            .data-grid {{
                display: grid;
                grid-template-columns: 150px 1fr;
                gap: 10px 20px;
                margin-bottom: 15px;
            }}
            
            .data-label {{
                font-weight: 500;
                color: #666;
            }}
            
            .data-value {{
                font-family: monospace;
                color: #333;
            }}
            
            .url-box {{
                background: #f8f8f8;
                border: 1px solid #e5e5e5;
                padding: 12px;
                border-radius: 4px;
                font-family: monospace;
                font-size: 12px;
                word-break: break-all;
                color: #333;
            }}
            
            table {{
                width: 100%;
                border-collapse: collapse;
                border: 1px solid #e5e5e5;
                font-size: 14px;
            }}
            
            thead {{
                background: #f8f8f8;
            }}
            
            th {{
                padding: 12px;
                text-align: left;
                font-weight: 600;
                color: #333;
                border-bottom: 2px solid #e5e5e5;
            }}
            
            td {{
                padding: 10px 12px;
                border-bottom: 1px solid #f0f0f0;
                font-family: monospace;
                font-size: 13px;
            }}
            
            tr:last-child td {{
                border-bottom: none;
            }}
            
            tbody tr:hover {{
                background: #fafafa;
            }}
            
            .stats {{
                display: flex;
                gap: 20px;
                margin-bottom: 20px;
            }}
            
            .stat {{
                padding: 15px 20px;
                background: #f8f8f8;
                border-radius: 4px;
                border: 1px solid #e5e5e5;
            }}
            
            .stat-label {{
                font-size: 12px;
                color: #666;
                text-transform: uppercase;
                font-weight: 500;
                margin-bottom: 5px;
            }}
            
            .stat-value {{
                font-size: 24px;
                color: #333;
                font-weight: 600;
            }}
            
            .status-badge {{
                display: inline-block;
                padding: 4px 12px;
                background: #10b981;
                color: white;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 600;
            }}
            
            .links {{
                margin-top: 25px;
                padding-top: 20px;
                border-top: 1px solid #e5e5e5;
            }}
            
            .link {{
                display: inline-block;
                color: #3b82f6;
                text-decoration: none;
                font-weight: 500;
                margin-right: 20px;
                font-size: 14px;
            }}
            
            .link:hover {{
                text-decoration: underline;
            }}
            
            .refresh-btn {{
                background: #3b82f6;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: 500;
                cursor: pointer;
                font-size: 14px;
                margin-bottom: 15px;
            }}
            
            .refresh-btn:hover {{
                background: #2563eb;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Job Done Report</h1>
            <p class="subtitle"><span class="status-badge">SUCCESS</span> Report received and processed</p>
            
            <div class="section">
                <div class="section-title">Current Report</div>
                <div class="data-grid">
                    <div class="data-label">Machine:</div>
                    <div class="data-value">{m}</div>
                    
                    <div class="data-label">Job Number:</div>
                    <div class="data-value">{c}</div>
                    
                    <div class="data-label">Step:</div>
                    <div class="data-value">{s}</div>
                    
                    <div class="data-label">Timestamp:</div>
                    <div class="data-value">{timestamp}</div>
                    
                    <div class="data-label">Client IP:</div>
                    <div class="data-value">{client_ip}</div>
                    
                    <div class="data-label">User Agent:</div>
                    <div class="data-value">{user_agent}</div>
                </div>
                
                <div style="margin-top: 12px;">
                    <div class="data-label" style="margin-bottom: 8px;">Request URL:</div>
                    <div class="url-box">{full_url}</div>
                </div>
            </div>
            
            <div class="section">
                <div class="section-title">Recent History</div>
                
                <div class="stats">
                    <div class="stat">
                        <div class="stat-label">Total Reports</div>
                        <div class="stat-value">{len(recent_reports)}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Showing</div>
                        <div class="stat-value">{min(20, len(recent_reports))}</div>
                    </div>
                </div>
                
                <button class="refresh-btn" onclick="location.reload()">Refresh</button>
                
                <table>
                    <thead>
                        <tr>
                            <th>Timestamp</th>
                            <th>Machine</th>
                            <th>Job Number</th>
                            <th>Step</th>
                        </tr>
                    </thead>
                    <tbody>
                        {history_rows}
                    </tbody>
                </table>
            </div>
            
            <div class="links">
                <a href="/" class="link">← Home</a>
                <a href="/monitor" class="link">Monitor</a>
            </div>
        </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)


