# User Account Install Notes

## Current installer behavior

When installing ERP-CNC Adapter, the option to run the adapter as a Windows user should be enabled by default. Keep it enabled when installing for the machine operator or another account that needs CNC file access.

Use this option when the adapter needs access to files, folders, mapped drives, or UNC/network shares that are available to that Windows user but not to the default `SYSTEM` account. Untick it only when the adapter should deliberately run as `SYSTEM`.

If the selected Windows user account has no password, Windows Task Scheduler cannot create a boot-time task that stores credentials for that account. In that case, the installer falls back to an interactive logon task:

- The adapter starts when the selected user logs on.
- The adapter does not start before login.
- The watchdog task may not be created because it still needs stored task credentials.

For true boot-time startup under a Windows user account, that account needs a password. Otherwise, install as `SYSTEM` or use the logon-only behavior.

## Future change

The installer should continue treating the Windows user install path as the default behavior.

Future installer work should:

- Make the "run as Windows user" choice more prominent during installation.
- Clearly explain the difference between `SYSTEM`, password-backed user startup, and passwordless logon-only startup.
- Avoid presenting the passwordless fallback as normal boot-time startup.
- Handle or message watchdog behavior for passwordless user accounts.
