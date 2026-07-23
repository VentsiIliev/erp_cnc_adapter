"""Tests for dashboard template controls."""

from pathlib import Path


def _dashboard_html() -> str:
    return (
        Path(__file__).resolve().parent.parent
        / "src"
        / "web"
        / "templates"
        / "dashboard.html"
    ).read_text(encoding="utf-8")


def test_testing_section_has_unload_job_button():
    dashboard = _dashboard_html()

    assert 'id="unloadJobBtn"' in dashboard
    assert "Unload Job" in dashboard


def test_unload_job_button_gets_unload_endpoint():
    dashboard = _dashboard_html()

    assert "async function unloadReferenceJob()" in dashboard
    assert 'fetchJson("/api/cnc/job/unload")' in dashboard
    assert 'document.getElementById("unloadJobBtn").addEventListener("click", unloadReferenceJob)' in dashboard


def test_hero_shows_machine_id_and_adapter_ip():
    dashboard = _dashboard_html()

    assert "Machine ID" in dashboard
    assert 'id="heroMachineId"' in dashboard
    assert "Adapter IP" in dashboard
    assert 'id="heroAdapterIp"' in dashboard
    assert 'document.getElementById("heroMachineId").textContent = body.machine_number;' in dashboard
    assert 'const adapterAddress = (body.local_ip || body.host) + ":" + body.port;' in dashboard
    assert 'document.getElementById("heroAdapterIp").textContent = adapterAddress;' in dashboard
    assert 'id="heroBindAddress"' in dashboard


def test_config_form_can_edit_adapter_port():
    dashboard = _dashboard_html()

    assert 'label for="adapterPort"' in dashboard
    assert 'id="adapterPort"' in dashboard
    assert 'id="currentAdapterPort"' in dashboard
    assert 'const adapterPort = document.getElementById("adapterPort").value;' in dashboard
    assert 'if (adapterPort) payload.port = parseInt(adapterPort, 10);' in dashboard
    assert '"adapterPort"' in dashboard


def test_config_form_can_toggle_adapter_logon_start():
    dashboard = _dashboard_html()

    assert 'id="autoStartAdapterOnLogonToggle"' in dashboard
    assert 'id="currentAutoStartAdapterOnLogon"' in dashboard
    assert 'id="adapterStartupDelay"' in dashboard
    assert 'id="currentAdapterStartupDelay"' in dashboard
    assert "body.auto_start_adapter_on_logon ? \"Enabled\" : \"Disabled\"" in dashboard
    assert "payload.auto_start_adapter_on_logon = autoStartAdapterOnLogon;" in dashboard
    assert "payload.adapter_startup_delay_seconds = parseInt(adapterStartupDelay, 10);" in dashboard


def test_dashboard_response_disables_cache():
    from src.api.dashboard_page import dashboard_response

    response = dashboard_response("testing")

    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["expires"] == "0"
    assert 'const INITIAL_VIEW = "testing"' in response.body.decode("utf-8")
