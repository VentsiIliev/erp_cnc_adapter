"""Standalone multi-machine health dashboard for ERP-CNC Adapter instances."""

from __future__ import annotations

import json
import socket
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "machines.json"
HISTORY_PATH = APP_DIR / "health_history.json"
DEFAULT_PORT = 8010


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    config.setdefault("poll_interval_seconds", 10)
    config.setdefault("request_timeout_seconds", 2)
    config.setdefault("machines", [])
    return config


def machine_base_url(machine: dict[str, Any]) -> str:
    host = str(machine["host"]).strip()
    port = int(machine.get("port", 8002))
    return f"http://{host}:{port}"


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_history(path: Path = HISTORY_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"current": {}, "events": []}
    try:
        with path.open("r", encoding="utf-8") as handle:
            history = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {"current": {}, "events": []}
    history.setdefault("current", {})
    history.setdefault("events", [])
    return history


def save_history(history: dict[str, Any], path: Path = HISTORY_PATH) -> None:
    path.write_text(json.dumps(history, indent=2), encoding="utf-8")


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def duration_seconds(started_at: str | None, ended_at: str | None) -> int | None:
    start = parse_time(started_at)
    end = parse_time(ended_at)
    if start is None or end is None:
        return None
    return max(0, int((end - start).total_seconds()))


def outage_status(machine: dict[str, Any]) -> str:
    if machine.get("connected"):
        return "connected"
    if machine.get("online"):
        return "degraded"
    return "offline"


def update_outage_history(
    machines: list[dict[str, Any]],
    history: dict[str, Any] | None = None,
    checked_at: str | None = None,
) -> dict[str, Any]:
    history = history or {"current": {}, "events": []}
    current = history.setdefault("current", {})
    events = history.setdefault("events", [])
    checked_at = checked_at or now_text()
    changed = False

    recent_by_machine: dict[str, dict[str, Any]] = {}
    for event in reversed(events):
        machine_id = event.get("machine_id")
        if machine_id and machine_id not in recent_by_machine:
            recent_by_machine[machine_id] = event

    for machine in machines:
        machine_id = str(machine["id"])
        status = outage_status(machine)
        active = current.get(machine_id)

        if status == "connected":
            if active:
                active["ended_at"] = checked_at
                active["duration_seconds"] = duration_seconds(active.get("started_at"), checked_at)
                events.append(active)
                current.pop(machine_id, None)
                recent_by_machine[machine_id] = active
                changed = True
        else:
            if not active:
                active = {
                    "machine_id": machine_id,
                    "started_at": checked_at,
                    "start_status": status,
                    "last_status": status,
                    "last_error": machine.get("last_error"),
                }
                current[machine_id] = active
                changed = True
            elif active.get("last_status") != status or active.get("last_error") != machine.get("last_error"):
                active["last_status"] = status
                active["last_error"] = machine.get("last_error")
                changed = True

            machine["current_outage_started_at"] = active.get("started_at")
            machine["current_outage_duration_seconds"] = duration_seconds(active.get("started_at"), checked_at)

        last_event = recent_by_machine.get(machine_id)
        machine["outage_count"] = sum(1 for event in events if event.get("machine_id") == machine_id)
        machine["last_outage_started_at"] = last_event.get("started_at") if last_event else None
        machine["last_outage_ended_at"] = last_event.get("ended_at") if last_event else None
        machine["last_outage_duration_seconds"] = last_event.get("duration_seconds") if last_event else None

        if status == "connected":
            machine["current_outage_started_at"] = None
            machine["current_outage_duration_seconds"] = None

    history["_changed"] = changed
    return history


def fetch_machine_health(machine: dict[str, Any], timeout: float) -> dict[str, Any]:
    started = time.monotonic()
    base_url = machine_base_url(machine)
    url = f"{base_url}/api/health"
    result = {
        "id": machine.get("id", machine.get("host", "Unknown")),
        "host": machine.get("host", ""),
        "port": int(machine.get("port", 8002)),
        "dashboard_url": f"{base_url}/dashboard",
        "health_url": url,
        "online": False,
        "status": "offline",
        "connected": False,
        "cnc_state": "offline",
        "machine_state_text": None,
        "retry_count": None,
        "last_error": None,
        "uptime_seconds": None,
        "response_ms": None,
        "checked_at": now_text(),
        "current_outage_started_at": None,
        "current_outage_duration_seconds": None,
        "last_outage_started_at": None,
        "last_outage_ended_at": None,
        "last_outage_duration_seconds": None,
        "outage_count": 0,
    }

    try:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        result["last_error"] = str(exc)
        result["response_ms"] = round((time.monotonic() - started) * 1000)
        return result

    cnc = payload.get("cnc", {})
    result.update(
        {
            "online": True,
            "status": payload.get("status", "unknown"),
            "connected": bool(cnc.get("connected")),
            "cnc_state": cnc.get("state") or "unknown",
            "machine_state_text": cnc.get("machine_state_text"),
            "retry_count": cnc.get("retry_count"),
            "last_error": cnc.get("last_error"),
            "uptime_seconds": cnc.get("uptime_seconds"),
            "response_ms": round((time.monotonic() - started) * 1000),
        }
    )
    return result


def collect_health(config: dict[str, Any]) -> dict[str, Any]:
    machines = list(config.get("machines", []))
    timeout = float(config.get("request_timeout_seconds", 2))
    results = []

    with ThreadPoolExecutor(max_workers=max(1, min(12, len(machines)))) as executor:
        futures = [executor.submit(fetch_machine_health, machine, timeout) for machine in machines]
        for future in as_completed(futures):
            results.append(future.result())

    order = {machine.get("id"): index for index, machine in enumerate(machines)}
    results.sort(key=lambda item: order.get(item["id"], 999))
    checked_at = now_text()
    history = update_outage_history(results, load_history(), checked_at)
    if history.pop("_changed", False):
        save_history(history)

    connected = sum(1 for item in results if item["connected"])
    online = sum(1 for item in results if item["online"])

    return {
        "poll_interval_seconds": int(config.get("poll_interval_seconds", 10)),
        "checked_at": checked_at,
        "summary": {
            "total": len(results),
            "online": online,
            "connected": connected,
            "degraded": online - connected,
            "offline": len(results) - online,
        },
        "machines": results,
    }


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Plant Machine Health</title>
  <style>
    :root {
      --bg: #f5f7fb;
      --panel: #ffffff;
      --text: #172033;
      --muted: #697386;
      --border: #d9e0ea;
      --green: #138a43;
      --green-bg: #e5f7eb;
      --amber: #a15c00;
      --amber-bg: #fff2d6;
      --red: #b42318;
      --red-bg: #ffe4e1;
      --blue: #155eef;
      --shadow: 0 14px 35px rgba(20, 33, 61, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Segoe UI, Arial, sans-serif;
    }
    header {
      padding: 22px 28px 14px;
      background: var(--panel);
      border-bottom: 1px solid var(--border);
    }
    .topline {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 18px;
      flex-wrap: wrap;
    }
    h1 {
      margin: 0;
      font-size: 26px;
      line-height: 1.2;
      font-weight: 700;
      letter-spacing: 0;
    }
    .sub {
      margin-top: 6px;
      color: var(--muted);
      font-size: 14px;
    }
    .summary {
      display: grid;
      grid-template-columns: repeat(4, minmax(110px, 1fr));
      gap: 10px;
      margin-top: 18px;
      max-width: 760px;
    }
    .metric {
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 12px;
      background: #fbfcff;
    }
    .metric strong {
      display: block;
      font-size: 22px;
      line-height: 1.1;
    }
    .metric span {
      color: var(--muted);
      font-size: 12px;
    }
    main { padding: 24px 28px 34px; }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 14px;
    }
    .machine {
      display: block;
      min-height: 178px;
      padding: 16px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--panel);
      color: inherit;
      text-decoration: none;
      box-shadow: var(--shadow);
      transition: transform 0.12s ease, border-color 0.12s ease;
    }
    .machine:hover {
      transform: translateY(-1px);
      border-color: #98a7bc;
    }
    .row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }
    .name {
      font-size: 22px;
      font-weight: 700;
      letter-spacing: 0;
    }
    .pill {
      border-radius: 999px;
      padding: 5px 9px;
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }
    .ready .pill { color: var(--green); background: var(--green-bg); }
    .degraded .pill { color: var(--amber); background: var(--amber-bg); }
    .offline .pill { color: var(--red); background: var(--red-bg); }
    .meta {
      margin-top: 14px;
      display: grid;
      gap: 7px;
      color: var(--muted);
      font-size: 13px;
    }
    .meta b { color: var(--text); font-weight: 600; }
    .error {
      margin-top: 12px;
      color: var(--red);
      font-size: 13px;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }
    .actions {
      margin-top: 14px;
      color: var(--blue);
      font-size: 13px;
      font-weight: 600;
    }
    button {
      border: 1px solid var(--border);
      background: var(--panel);
      color: var(--text);
      border-radius: 8px;
      padding: 9px 12px;
      cursor: pointer;
      font: inherit;
      font-weight: 600;
    }
    button:hover { border-color: #98a7bc; }
    .statusline {
      color: var(--muted);
      font-size: 13px;
      margin-top: 14px;
    }
    @media (max-width: 640px) {
      header, main { padding-left: 16px; padding-right: 16px; }
      .summary { grid-template-columns: repeat(2, 1fr); }
    }
  </style>
</head>
<body>
  <header>
    <div class="topline">
      <div>
        <h1>Plant Machine Health</h1>
        <div class="sub">Polling adapter health endpoints across CNC machines.</div>
      </div>
      <button type="button" id="refreshBtn">Refresh</button>
    </div>
    <div class="summary">
      <div class="metric"><strong id="connectedCount">--</strong><span>Connected</span></div>
      <div class="metric"><strong id="degradedCount">--</strong><span>Degraded</span></div>
      <div class="metric"><strong id="offlineCount">--</strong><span>Offline</span></div>
      <div class="metric"><strong id="totalCount">--</strong><span>Total</span></div>
    </div>
    <div class="statusline" id="statusLine">Loading machine health...</div>
  </header>
  <main>
    <section class="grid" id="machineGrid"></section>
  </main>
  <script>
    const grid = document.getElementById("machineGrid");
    const statusLine = document.getElementById("statusLine");
    const refreshBtn = document.getElementById("refreshBtn");
    let pollTimer = null;

    function formatUptime(seconds) {
      if (seconds === null || seconds === undefined) return "--";
      const s = Math.max(0, Math.floor(seconds));
      if (s < 60) return `${s}s`;
      if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
      return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
    }

    function formatOutage(machine) {
      if (machine.current_outage_started_at) {
        return `Since ${machine.current_outage_started_at} (${formatUptime(machine.current_outage_duration_seconds)})`;
      }
      if (machine.last_outage_ended_at) {
        return `${machine.last_outage_started_at} to ${machine.last_outage_ended_at} (${formatUptime(machine.last_outage_duration_seconds)})`;
      }
      return "--";
    }

    function classFor(machine) {
      if (machine.connected) return "ready";
      if (machine.online) return "degraded";
      return "offline";
    }

    function labelFor(machine) {
      if (machine.connected) return "Connected";
      if (machine.online) return "Degraded";
      return "Offline";
    }

    function render(data) {
      document.getElementById("connectedCount").textContent = data.summary.connected;
      document.getElementById("degradedCount").textContent = data.summary.degraded;
      document.getElementById("offlineCount").textContent = data.summary.offline;
      document.getElementById("totalCount").textContent = data.summary.total;
      statusLine.textContent = `Last checked ${data.checked_at}. Refreshes every ${data.poll_interval_seconds}s.`;

      grid.innerHTML = "";
      for (const machine of data.machines) {
        const stateClass = classFor(machine);
        const card = document.createElement("a");
        card.className = `machine ${stateClass}`;
        card.href = machine.dashboard_url;
        card.target = "_blank";
        card.rel = "noopener";
        card.innerHTML = `
          <div class="row">
            <div class="name">${machine.id}</div>
            <div class="pill">${labelFor(machine)}</div>
          </div>
          <div class="meta">
            <div><b>Address</b> ${machine.host}:${machine.port}</div>
            <div><b>CNC state</b> ${machine.cnc_state || "--"}</div>
            <div><b>Interpreter</b> ${machine.machine_state_text || "--"}</div>
            <div><b>Uptime</b> ${formatUptime(machine.uptime_seconds)}</div>
            <div><b>Outage</b> ${formatOutage(machine)}</div>
            <div><b>Outages recorded</b> ${machine.outage_count || 0}</div>
            <div><b>Response</b> ${machine.response_ms == null ? "--" : machine.response_ms + " ms"}</div>
          </div>
          ${machine.last_error ? `<div class="error">${machine.last_error}</div>` : ""}
          <div class="actions">Open machine dashboard</div>
        `;
        grid.appendChild(card);
      }

      clearTimeout(pollTimer);
      pollTimer = setTimeout(load, Math.max(5, data.poll_interval_seconds) * 1000);
    }

    async function load() {
      refreshBtn.disabled = true;
      try {
        const response = await fetch("/api/machines", { cache: "no-store" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        render(await response.json());
      } catch (error) {
        statusLine.textContent = `Refresh failed: ${error.message}`;
      } finally {
        refreshBtn.disabled = false;
      }
    }

    refreshBtn.addEventListener("click", load);
    load();
  </script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self) -> None:
        body = INDEX_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            self._send_html()
            return
        if self.path == "/api/machines":
            self._send_json(collect_health(load_config()))
            return
        self._send_json({"error": "Not found"}, status=404)

    def log_message(self, format: str, *args: Any) -> None:
        print("%s - %s" % (self.address_string(), format % args))


def local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    server = ThreadingHTTPServer(("0.0.0.0", port), DashboardHandler)
    print(f"Machine health dashboard: http://127.0.0.1:{port}")
    print(f"Network address: http://{local_ip()}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
