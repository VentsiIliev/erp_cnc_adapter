# Update Page

## Overview

The ERP-CNC Adapter now has a **dedicated update page** for managing adapter updates and rollbacks. This resolves issues where file selection on the health page could interfere with the page's auto-refresh functionality.

## Accessing the Update Page

- **URL**: `http://localhost:8000/update`
- **Link**: Click "Update Adapter" button at the bottom of the health page

## Features

### 📦 Upload New Version

Upload a new ERP-CNC Adapter executable (`.exe` file) to update the service:

1. Click or drag-and-drop an `.exe` file into the upload area
2. Click "Upload & Update" button
3. The service will automatically restart with the new version

**Important**: The service restarts during the update process. Any active CNC operations will be interrupted. Updates typically complete in 5-10 seconds.

### ⏮️ Rollback

Restore a previous version from automatic backups:

1. Click "Rollback to Previous Version" button
2. Confirm the rollback action
3. The service will restart with the most recent backup

### Available Backups

View all available backup files:
- Automatically created before each update
- Up to 5 backups are retained (older ones are automatically removed)
- Each backup shows filename and size

## Technical Details

### Routes

- `GET /update` - Dedicated update page (HTML)
- `POST /api/update` - Upload new version (API endpoint)
- `POST /api/update/rollback` - Rollback to previous version
- `GET /api/update/backups` - List available backups

### File Structure

- **Handler**: `src/handlers/update_page.py` - Dedicated update page UI
- **API Handler**: `src/handlers/update.py` - Update/rollback API endpoints
- **Tests**: `tests/test_update_page.py` - Update page tests

### Changes from Previous Version

**Before:**
- Update form was embedded in the health page
- File selection could interfere with health page auto-refresh
- Cluttered UI on the main health status page

**After:**
- Dedicated update page with clear UI
- No interference with health page functionality
- Better user experience with drag-and-drop support
- Clear warnings about service restart
- Back navigation to health page

## User Interface

The update page features:
- 📁 Drag-and-drop file upload area
- ⚠️ Warning about service restart
- ✓ Visual feedback for file selection
- 📋 Backup list with file sizes
- ← Navigation back to health page
- 🔗 Links to API documentation

## Backup Management

Backups are automatically managed:
- Created before each successful update
- Named: `erp-cnc-adapter.exe.bak.YYYYMMDD_HHMMSS`
- Maximum 5 backups retained
- Oldest backups automatically deleted

## Testing

Run update page tests:
```bash
python -m pytest tests/test_update_page.py -v
```

All tests (74 total, including 6 for update page):
```bash
python -m pytest tests/ -v
```

