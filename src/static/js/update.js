const msg = document.getElementById('updateMsg');
const fileInput = document.getElementById('exeFile');
const fileWrapper = document.getElementById('fileWrapper');
const updateBtn = document.getElementById('updateBtn');
const selectedFileName = document.getElementById('selectedFileName');

function showMsg(text, ok) {
  msg.textContent = text;
  msg.className = 'update-msg ' + (ok ? 'ok' : 'err');
  if (ok) {
    setTimeout(() => {
      msg.className = 'update-msg';
    }, 10000);
  }
}

// File selection handling
fileInput.addEventListener('change', function() {
  if (this.files.length > 0) {
    const file = this.files[0];
    fileWrapper.classList.add('has-file');
    selectedFileName.textContent = '\u2713 ' + file.name + ' (' + (file.size / (1024*1024)).toFixed(2) + ' MB)';
    updateBtn.disabled = false;
  } else {
    fileWrapper.classList.remove('has-file');
    selectedFileName.textContent = '';
    updateBtn.disabled = true;
  }
});

// Drag and drop
fileWrapper.addEventListener('dragover', function(e) {
  e.preventDefault();
  this.style.borderColor = '#3b82f6';
});

fileWrapper.addEventListener('dragleave', function(e) {
  e.preventDefault();
  if (!fileWrapper.classList.contains('has-file')) {
    this.style.borderColor = '#cbd5e1';
  }
});

fileWrapper.addEventListener('drop', function(e) {
  e.preventDefault();
  const dt = e.dataTransfer;
  if (dt.files.length > 0) {
    fileInput.files = dt.files;
    fileInput.dispatchEvent(new Event('change'));
  }
});

// Upload & Update
document.getElementById('updateForm').addEventListener('submit', async function(e) {
  e.preventDefault();
  if (!fileInput.files.length) return;

  updateBtn.disabled = true;
  const originalText = updateBtn.textContent;
  updateBtn.textContent = 'Uploading...';
  msg.className = 'update-msg';

  try {
    const fd = new FormData();
    fd.append('file', fileInput.files[0]);
    const res = await fetch('/api/update', { method: 'POST', body: fd });
    const text = await res.text();
    let data;
    try { data = JSON.parse(text); } catch { data = { status: 1, message: text || ('Server error: ' + res.status) }; }
    showMsg(data.message + (data.version_info ? ' (' + data.version_info + ')' : ''), data.status === 0);

    if (data.status === 0) {
      // Clear file selection on success
      fileInput.value = '';
      fileWrapper.classList.remove('has-file');
      selectedFileName.textContent = '';
    }
  } catch(err) {
    showMsg('Upload failed: ' + err.message, false);
    updateBtn.disabled = false;
  }

  updateBtn.textContent = originalText;
  loadBackups();
});

// Rollback
document.getElementById('rollbackBtn').addEventListener('click', async function() {
  if (!confirm('Are you sure you want to rollback to the most recent backup?\n\nThe service will restart with the previous version.')) return;

  const btn = this;
  btn.disabled = true;
  const originalText = btn.textContent;
  btn.textContent = 'Rolling back...';
  msg.className = 'update-msg';

  try {
    const res = await fetch('/api/update/rollback', { method: 'POST' });
    const text = await res.text();
    let data;
    try { data = JSON.parse(text); } catch { data = { status: 1, message: text || ('Server error: ' + res.status) }; }
    showMsg(data.message, data.status === 0);
  } catch(err) {
    showMsg('Rollback failed: ' + err.message, false);
  }

  btn.disabled = false;
  btn.textContent = originalText;
  loadBackups();
});

// Load backups
async function loadBackups() {
  try {
    const res = await fetch('/api/update/backups');
    const data = await res.json();
    const ul = document.getElementById('backupList');
    if (!data.backups || data.backups.length === 0) {
      ul.innerHTML = '<li><span class="backup-name">No backups available</span></li>';
    } else {
      ul.innerHTML = data.backups.map(function(b) {
        return '<li><span class="backup-name">' + b.filename + '</span><span class="backup-size">' + b.size_mb + ' MB</span></li>';
      }).join('');
    }
  } catch(e) {
    document.getElementById('backupList').innerHTML = '<li><span class="backup-name">Failed to load backups</span></li>';
  }
}

loadBackups();
