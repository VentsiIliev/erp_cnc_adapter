# CREATE_NO_WINDOW Fix - Version 1.0.9

## The Problem with VBScript

VBScript was created successfully but the Python process never actually started. This is likely because:
1. VBScript execution policies or permissions
2. Security restrictions from running within a service
3. VBScript's `Run(..., 0, False)` doesn't actually detach properly in this context

## The CREATE_NO_WINDOW Solution

Instead of using VBScript, we're now using Python's subprocess with the **CREATE_NO_WINDOW** flag directly:

```python
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200

subprocess.Popen(
    [python_exe, worker, ...],
    creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
    close_fds=False,  # Allow process to run independently
)
```

### Why This Should Work

1. **CREATE_NO_WINDOW (0x08000000)**: Creates process without console window
2. **CREATE_NEW_PROCESS_GROUP (0x00000200)**: New process group (survives parent)
3. **close_fds=False**: Allows child to run independently
4. **Direct execution**: No VBScript intermediary

This is the **native Windows way** to spawn background processes from Python.

## Version 1.0.9

Building now with this fix. This approach:
- ✅ No VBScript needed
- ✅ No batch files
- ✅ Direct Python subprocess call
- ✅ Proper Windows process creation flags
- ✅ Should work from service context

## Testing Plan

1. Install v1.0.9
2. Upload v1.0.9 EXE (self-update test)
3. Check for `logs/update.log` creation
4. If successful, build v1.0.10 and test version change

## Why Previous Methods Failed

| Method | Issue |
|--------|-------|
| DETACHED_PROCESS alone | Didn't work from PyInstaller |
| cmd.exe START | Process didn't actually start |
| Batch file | Same as cmd.exe |
| VBScript | Process didn't start (permission/policy?) |
| **CREATE_NO_WINDOW + CREATE_NEW_PROCESS_GROUP** | ✅ Should work! |

## Expected Behavior

After uploading update:
1. Process spawns with no console window
2. Process runs in new process group
3. `logs/update.log` gets created
4. Service stops, EXE replaced, service restarts
5. Version updates

The key indicator is still: **Does `logs/update.log` get created?**

