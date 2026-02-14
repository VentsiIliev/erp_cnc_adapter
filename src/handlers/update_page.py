"""
Update Page Handler - Dedicated page for adapter updates
"""
import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from version import VERSION

logger = logging.getLogger(__name__)
router = APIRouter()


def _render_update_page() -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Update - ERP-CNC Adapter</title>
<link rel="icon" href="/favicon.ico" type="image/x-icon">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f1f5f9;
    color: #1e293b;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }}
  .card {{
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,.1), 0 4px 16px rgba(0,0,0,.06);
    width: 520px;
    max-width: 95vw;
    overflow: hidden;
  }}
  .header {{
    padding: 24px 28px 20px;
    border-bottom: 1px solid #e2e8f0;
  }}
  .header h1 {{
    font-size: 18px;
    font-weight: 600;
    color: #334155;
  }}
  .header .version {{
    font-size: 13px;
    color: #94a3b8;
    margin-top: 2px;
  }}
  .back-link {{
    display: inline-block;
    margin-bottom: 12px;
    color: #3b82f6;
    text-decoration: none;
    font-size: 14px;
  }}
  .back-link:hover {{ text-decoration: underline; }}
  .content {{
    padding: 24px 28px;
  }}
  .section {{
    margin-bottom: 28px;
  }}
  .section:last-child {{
    margin-bottom: 0;
  }}
  .section h2 {{
    font-size: 15px;
    font-weight: 600;
    color: #475569;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .section p {{
    font-size: 14px;
    color: #64748b;
    line-height: 1.6;
    margin-bottom: 12px;
  }}
  .update-form {{
    display: flex;
    flex-direction: column;
    gap: 12px;
  }}
  .file-input-wrapper {{
    position: relative;
    border: 2px dashed #cbd5e1;
    border-radius: 8px;
    padding: 24px;
    text-align: center;
    transition: border-color .2s;
    cursor: pointer;
    background: #f8fafc;
  }}
  .file-input-wrapper:hover {{
    border-color: #94a3b8;
  }}
  .file-input-wrapper.has-file {{
    border-color: #3b82f6;
    background: #eff6ff;
  }}
  .file-input-wrapper input[type="file"] {{
    position: absolute;
    width: 100%;
    height: 100%;
    top: 0;
    left: 0;
    opacity: 0;
    cursor: pointer;
  }}
  .file-placeholder {{
    pointer-events: none;
  }}
  .file-icon {{
    font-size: 32px;
    margin-bottom: 8px;
    color: #94a3b8;
  }}
  .file-input-wrapper.has-file .file-icon {{
    color: #3b82f6;
  }}
  .file-text {{
    font-size: 14px;
    color: #64748b;
    font-weight: 500;
  }}
  .file-input-wrapper.has-file .file-text {{
    color: #2563eb;
  }}
  .file-subtext {{
    font-size: 12px;
    color: #94a3b8;
    margin-top: 4px;
  }}
  .selected-file {{
    display: none;
    font-size: 13px;
    color: #475569;
    margin-top: 8px;
    font-weight: 500;
  }}
  .file-input-wrapper.has-file .selected-file {{
    display: block;
  }}
  .button-group {{
    display: flex;
    gap: 10px;
    align-items: center;
  }}
  .update-btn {{
    flex: 1;
    padding: 12px 24px;
    background: #f59e0b;
    color: #fff;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: background .15s;
  }}
  .update-btn:hover {{ background: #d97706; }}
  .update-btn:disabled {{
    background: #cbd5e1;
    cursor: not-allowed;
  }}
  .rollback-btn {{
    padding: 12px 24px;
    background: #6366f1;
    color: #fff;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: background .15s;
  }}
  .rollback-btn:hover {{ background: #4f46e5; }}
  .update-msg {{
    font-size: 14px;
    padding: 12px 16px;
    border-radius: 8px;
    display: none;
    line-height: 1.5;
  }}
  .update-msg.ok {{ display: block; background: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }}
  .update-msg.err {{ display: block; background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }}
  .backup-list {{
    margin-top: 12px;
    padding: 16px;
    background: #f8fafc;
    border-radius: 8px;
    border: 1px solid #e2e8f0;
  }}
  .backup-list summary {{
    cursor: pointer;
    font-weight: 600;
    color: #475569;
    font-size: 14px;
    list-style: none;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .backup-list summary::-webkit-details-marker {{
    display: none;
  }}
  .backup-list summary::before {{
    content: '▸';
    display: inline-block;
    transition: transform .2s;
  }}
  .backup-list[open] summary::before {{
    transform: rotate(90deg);
  }}
  .backup-list ul {{
    list-style: none;
    padding: 12px 0 0 0;
  }}
  .backup-list li {{
    padding: 8px 12px;
    font-size: 13px;
    color: #64748b;
    background: #fff;
    border-radius: 6px;
    margin-bottom: 6px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .backup-list li:last-child {{
    margin-bottom: 0;
  }}
  .backup-name {{
    font-family: monospace;
    color: #475569;
  }}
  .backup-size {{
    font-size: 12px;
    color: #94a3b8;
  }}
  .warning-box {{
    padding: 14px 16px;
    background: #fef3c7;
    border: 1px solid #fde68a;
    border-radius: 8px;
    font-size: 13px;
    color: #92400e;
    line-height: 1.6;
  }}
  .warning-box strong {{
    display: block;
    margin-bottom: 4px;
    color: #78350f;
  }}
  .footer {{
    padding: 16px 28px;
    border-top: 1px solid #e2e8f0;
    text-align: center;
    font-size: 12px;
    color: #94a3b8;
  }}
  .footer a {{
    color: #64748b;
    text-decoration: none;
  }}
  .footer a:hover {{ text-decoration: underline; }}
  .nav-links {{
    display: flex;
    gap: 12px;
    justify-content: center;
    flex-wrap: wrap;
  }}
</style>
</head>
<body>
  <div class="card">
    <div class="header">
      <a href="/" class="back-link">← Back to Health</a>
      <h1>Update Adapter</h1>
      <div class="version">Current: v{VERSION}</div>
    </div>
    
    <div class="content">
      <div class="section">
        <h2>📦 Upload New Version</h2>
        <p>Upload a new ERP-CNC Adapter executable to update the service. The adapter will automatically restart with the new version.</p>
        
        <div class="warning-box">
          <strong>⚠️ Important:</strong>
          The service will restart during the update process. Any active CNC operations will be interrupted. The update typically completes in 5-10 seconds.
        </div>

        <form class="update-form" id="updateForm">
          <div class="file-input-wrapper" id="fileWrapper">
            <input type="file" id="exeFile" accept=".exe" required>
            <div class="file-placeholder">
              <div class="file-icon">📁</div>
              <div class="file-text">Click to select .exe file</div>
              <div class="file-subtext">or drag and drop here</div>
              <div class="selected-file" id="selectedFileName"></div>
            </div>
          </div>
          <div class="button-group">
            <button type="submit" class="update-btn" id="updateBtn" disabled>Upload &amp; Update</button>
          </div>
        </form>
        <div class="update-msg" id="updateMsg"></div>
      </div>

      <div class="section">
        <h2>⏮️ Rollback</h2>
        <p>Restore a previous version from automatic backups. The most recent backup will be restored.</p>
        <button type="button" class="rollback-btn" id="rollbackBtn">Rollback to Previous Version</button>
        
        <details class="backup-list" id="backupDetails">
          <summary>Available backups</summary>
          <ul id="backupList"><li>Loading...</li></ul>
        </details>
      </div>
    </div>

    <div class="footer">
      <div class="nav-links">
        <a href="/">Health Status</a>
        &middot;
        <a href="/api/health">JSON API</a>
        &middot;
        <a href="/docs">API Docs</a>
      </div>
    </div>
  </div>

<script>
  const msg = document.getElementById('updateMsg');
  const fileInput = document.getElementById('exeFile');
  const fileWrapper = document.getElementById('fileWrapper');
  const updateBtn = document.getElementById('updateBtn');
  const selectedFileName = document.getElementById('selectedFileName');

  function showMsg(text, ok) {{
    msg.textContent = text;
    msg.className = 'update-msg ' + (ok ? 'ok' : 'err');
    if (ok) {{
      setTimeout(() => {{
        msg.className = 'update-msg';
      }}, 10000);
    }}
  }}

  // File selection handling
  fileInput.addEventListener('change', function() {{
    if (this.files.length > 0) {{
      const file = this.files[0];
      fileWrapper.classList.add('has-file');
      selectedFileName.textContent = '✓ ' + file.name + ' (' + (file.size / (1024*1024)).toFixed(2) + ' MB)';
      updateBtn.disabled = false;
    }} else {{
      fileWrapper.classList.remove('has-file');
      selectedFileName.textContent = '';
      updateBtn.disabled = true;
    }}
  }});

  // Drag and drop
  fileWrapper.addEventListener('dragover', function(e) {{
    e.preventDefault();
    this.style.borderColor = '#3b82f6';
  }});

  fileWrapper.addEventListener('dragleave', function(e) {{
    e.preventDefault();
    if (!fileWrapper.classList.contains('has-file')) {{
      this.style.borderColor = '#cbd5e1';
    }}
  }});

  fileWrapper.addEventListener('drop', function(e) {{
    e.preventDefault();
    const dt = e.dataTransfer;
    if (dt.files.length > 0) {{
      fileInput.files = dt.files;
      fileInput.dispatchEvent(new Event('change'));
    }}
  }});

  // Upload & Update
  document.getElementById('updateForm').addEventListener('submit', async function(e) {{
    e.preventDefault();
    if (!fileInput.files.length) return;
    
    updateBtn.disabled = true;
    const originalText = updateBtn.textContent;
    updateBtn.textContent = 'Uploading...';
    msg.className = 'update-msg';
    
    try {{
      const fd = new FormData();
      fd.append('file', fileInput.files[0]);
      const res = await fetch('/api/update', {{ method: 'POST', body: fd }});
      const text = await res.text();
      let data;
      try {{ data = JSON.parse(text); }} catch {{ data = {{ status: 1, message: text || ('Server error: ' + res.status) }}; }}
      showMsg(data.message + (data.version_info ? ' (' + data.version_info + ')' : ''), data.status === 0);

      if (data.status === 0) {{
        // Clear file selection on success
        fileInput.value = '';
        fileWrapper.classList.remove('has-file');
        selectedFileName.textContent = '';
      }}
    }} catch(err) {{
      showMsg('Upload failed: ' + err.message, false);
      updateBtn.disabled = false;
    }}
    
    updateBtn.textContent = originalText;
    loadBackups();
  }});

  // Rollback
  document.getElementById('rollbackBtn').addEventListener('click', async function() {{
    if (!confirm('Are you sure you want to rollback to the most recent backup?\\n\\nThe service will restart with the previous version.')) return;
    
    const btn = this;
    btn.disabled = true;
    const originalText = btn.textContent;
    btn.textContent = 'Rolling back...';
    msg.className = 'update-msg';
    
    try {{
      const res = await fetch('/api/update/rollback', {{ method: 'POST' }});
      const text = await res.text();
      let data;
      try {{ data = JSON.parse(text); }} catch {{ data = {{ status: 1, message: text || ('Server error: ' + res.status) }}; }}
      showMsg(data.message, data.status === 0);
    }} catch(err) {{
      showMsg('Rollback failed: ' + err.message, false);
    }}
    
    btn.disabled = false;
    btn.textContent = originalText;
    loadBackups();
  }});

  // Load backups
  async function loadBackups() {{
    try {{
      const res = await fetch('/api/update/backups');
      const data = await res.json();
      const ul = document.getElementById('backupList');
      if (!data.backups || data.backups.length === 0) {{
        ul.innerHTML = '<li><span class="backup-name">No backups available</span></li>';
      }} else {{
        ul.innerHTML = data.backups.map(function(b) {{
          return '<li><span class="backup-name">' + b.filename + '</span><span class="backup-size">' + b.size_mb + ' MB</span></li>';
        }}).join('');
      }}
    }} catch(e) {{
      document.getElementById('backupList').innerHTML = '<li><span class="backup-name">Failed to load backups</span></li>';
    }}
  }}
  
  loadBackups();
</script>
</body>
</html>"""


@router.get("/update")
async def update_page(request: Request):
    """Render the dedicated update page."""
    return HTMLResponse(content=_render_update_page())

