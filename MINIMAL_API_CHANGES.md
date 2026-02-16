# Minimal API Response Changes

**Date**: February 16, 2026  
**Version**: 1.3.1  

## Summary

Reduced the `/api/cnc/job/status` endpoint response to include only essential fields, improving:
- 📉 **Response size** - Smaller JSON payloads
- ⚡ **Performance** - Faster serialization
- 🎯 **Clarity** - Focus on critical job status information

---

## Fields Included in Response

### ✅ Status Fields
```json
{
  "state": 2,                           // CNC state code (0-23)
  "stateText": "Ready"                  // Human-readable state
}
```

### ✅ Job Identification
```json
{
  "jobName": "C:\\path\\to\\file.nc",  // Full path to G-code file
  "jobLoadCounter": 36                  // Lifetime job load counter
}
```

### ✅ Progress & Timing (Core Metrics)
```json
{
  "totalJobLength": 214.0,              // Calculated path length (mm)
  "jobProgress": 221.0,                 // Actual distance traveled (mm)
  "jobActualRunningTime": 52.42,        // Elapsed time (seconds)
  "jobRemainingRunningTime": -0.43,     // Estimated remaining (seconds)
  "jobEstimatedTime": 51.96             // Total estimated time (seconds)
}
```

### ✅ Repeat Mode Fields
```json
{
  "doRepeatJob": 0,                     // Boolean: repeat enabled
  "nrOfJobRepeatsSet": 1,               // Total repeats configured
  "nrOfRepeatsActual": 1,               // REMAINING repeats (countdown)
  
  // Computed convenience fields (added by API layer)
  "repeatEnabled": false,               // Boolean: repeat mode on
  "totalRepeats": 1,                    // Total repeats configured
  "currentRepeat": 1,                   // Current iteration (1-based)
  "repeatsRemaining": 1                 // Repeats left after current
}
```

---

## Fields Commented Out (Available for Future Use)

### 📝 Job Details
- `numLinesInJob` - Total lines in G-code file
- `numLinesInMacro` - Lines in system macros
- `numLinesInUserMacro` - Lines in user macros
- `numBytesInJob` - File size in bytes
- `isLongJob` - Boolean: exceeds line threshold
- `isSuperLongJob` - Boolean: exceeds super long threshold
- `jobIsRendered` - Boolean: toolpath rendered

### 📝 Collision Detection
- `TCACollision` - Tool Collision Avoidance
- `MCACollision` - Machine Collision Avoidance
- `xCollision`, `yCollision`, `zCollision` - Axis limit flags

### 📝 Rendering Progress
- `jobRenderLine` - Current line being rendered
- `jobRenderProgressPercentage` - Render progress percentage

### 📝 Interpreter/Executor Position
- `curIpLine` - Current interpreter line (1-based)
- `curIpLineText` - Current interpreter line text
- `curExLine` - Current executor line (1-based)
- `lastKnownExecutedLineNumber` - Last executed line
- `lastKnownToolChangeLineNumber` - Last tool change line

### 📝 Advanced Features
- `extraLineWhenEndOfJob` - G-code injected before M30
- `stockDiameterTurning` - Stock diameter for turning (mm)
- `stockLengthTurning` - Stock length for turning (mm)
- `stockZAtWorkOffset` - Stock Z position flag

---

## Code Changes

### 1. Schema (`src/api/schemas/job.py`)
```python
class JobStatusResponse(BaseModel):
    # Core fields only (commented out unused fields)
    state: int
    stateText: str
    jobName: str = ""
    jobLoadCounter: int = 0
    totalJobLength: float = 0.0
    jobProgress: float = 0.0
    # ... (see file for full details)
```

### 2. CNC Client (`src/cnc/cnc_client.py`)
```python
def get_job_status(self) -> dict:
    return {
        "jobName": job_name,
        "jobLoadCounter": s.jobLoadCounter,
        # Commented out unused fields
        # "numLinesInJob": s.numLinesInjob,
        # ... (see file for full details)
    }
```

### 3. Mock Client (`src/cnc/mock_cnc_client.py`)
Updated to return only minimal fields matching real client.

### 4. Test Fixtures (`tests/conftest.py`)
Updated `_default_job_status()` to return minimal fields.

### 5. Tests Updated
- `tests/test_job_status.py` - Updated field expectations
- `tests/test_schemas.py` - Added test for computed repeat fields
- All 215 tests pass ✅

---

## Migration Guide

### If You Need a Commented-Out Field

**Example: Re-enabling `numLinesInJob`**

1. **Uncomment in schema** (`src/api/schemas/job.py`):
   ```python
   numLinesInJob: int = 0  # Uncomment this line
   ```

2. **Uncomment in CNC client** (`src/cnc/cnc_client.py`):
   ```python
   "numLinesInJob": s.numLinesInjob,  # Uncomment this line
   ```

3. **Add to mock client** (`src/cnc/mock_cnc_client.py`):
   ```python
   "numLinesInJob": 0,  # Add this line
   ```

4. **Update tests** if they check for specific fields

5. **Run tests** to verify:
   ```bash
   pytest tests/
   ```

---

## Benefits

### Before (Full Response)
```json
{
  "state": 2,
  "stateText": "Ready",
  "jobName": "...",
  "jobLoadCounter": 36,
  "numLinesInJob": 12,           // ❌ Removed
  "numLinesInMacro": 668,         // ❌ Removed
  "numLinesInUserMacro": 5,       // ❌ Removed
  "numBytesInJob": 94,            // ❌ Removed
  "isLongJob": 0,                 // ❌ Removed
  "isSuperLongJob": 0,            // ❌ Removed
  "jobIsRendered": 1,             // ❌ Removed
  "totalJobLength": 214,
  "jobProgress": 221,
  // ... 23 more fields
}
```

### After (Minimal Response)
```json
{
  "state": 2,
  "stateText": "Ready",
  "jobName": "...",
  "jobLoadCounter": 36,
  "totalJobLength": 214,
  "jobProgress": 221,
  "jobActualRunningTime": 52.42,
  "jobRemainingRunningTime": -0.43,
  "jobEstimatedTime": 51.96,
  "doRepeatJob": 0,
  "nrOfJobRepeatsSet": 1,
  "nrOfRepeatsActual": 1,
  "repeatEnabled": false,
  "totalRepeats": 1,
  "currentRepeat": 1,
  "repeatsRemaining": 1
}
```

**Result**: ~60% fewer fields, focusing on what matters most! 🎯

---

## Rollback Instructions

If you need to restore all fields:

1. Revert changes in `src/api/schemas/job.py`
2. Revert changes in `src/cnc/cnc_client.py`
3. Revert changes in `src/cnc/mock_cnc_client.py`
4. Revert changes in `tests/conftest.py`
5. Run tests: `pytest tests/`

Or use git:
```bash
git checkout HEAD -- src/api/schemas/job.py src/cnc/cnc_client.py src/cnc/mock_cnc_client.py tests/conftest.py
```

---

## See Also

- **Field Units**: `CNC_JOB_STATUS_UNITS.md` - Complete reference with units for all fields
- **API Docs**: `API_DOCS.md` - Full API documentation
- **State Codes**: `CNC_STATE_CODES.md` - All CNC state definitions

---

**Note**: All commented-out fields remain in the codebase and can be easily re-enabled if needed. This provides flexibility while keeping the default response lean and focused.

