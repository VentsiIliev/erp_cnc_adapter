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
    assert 'const adapterPort = getConfigTextValue("adapterPort");' in dashboard
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

def test_dashboard_has_top_jog_pad_launcher_button():
    dashboard = _dashboard_html()

    assert 'id="openJogPadBtn"' in dashboard
    assert 'Open Jog Pad' in dashboard
    assert 'src="/favicon.ico"' in dashboard
    assert 'async function openJogPad()' in dashboard
    assert 'fetchJson("/api/jog-pad/open", { method: "POST" })' in dashboard
    assert 'document.getElementById("openJogPadBtn").addEventListener("click", openJogPad)' in dashboard


def test_config_form_can_edit_jog_pad_pause_hold_interval():
    dashboard = _dashboard_html()

    assert 'label for="jogPadPauseHoldInterval"' in dashboard
    assert 'id="jogPadPauseHoldInterval"' in dashboard
    assert 'id="currentJogPadPauseHoldInterval"' in dashboard
    assert 'const jogPadPauseHoldInterval = getConfigTextValue("jogPadPauseHoldInterval");' in dashboard
    assert 'payload.jog_pad_pause_hold_interval_ms = parseInt(jogPadPauseHoldInterval, 10);' in dashboard
    assert '"jogPadPauseHoldInterval"' in dashboard


def test_config_form_can_edit_cnc_share_credentials():
    dashboard = _dashboard_html()

    assert 'label for="cncShareUsername"' in dashboard
    assert 'id="cncShareUsername"' in dashboard
    assert 'id="currentCncShareUsername"' in dashboard
    assert 'label for="cncSharePassword"' in dashboard
    assert 'id="cncSharePassword"' in dashboard
    assert 'id="currentCncSharePasswordStatus"' in dashboard
    assert 'const cncShareUsername = getConfigTextValue("cncShareUsername").trim();' in dashboard
    assert 'const cncSharePassword = getConfigTextValue("cncSharePassword");' in dashboard
    assert 'payload.cnc_share_username = cncShareUsername;' in dashboard
    assert 'payload.cnc_share_password = cncSharePassword;' in dashboard
    assert '"cncShareUsername"' in dashboard
    assert '"cncSharePassword"' in dashboard


def test_config_form_can_edit_svn_update_credentials():
    dashboard = _dashboard_html()

    assert 'label for="updateUsername"' in dashboard
    assert 'id="updateUsername"' in dashboard
    assert 'id="currentUpdateUsername"' in dashboard
    assert 'label for="updatePassword"' in dashboard
    assert 'id="updatePassword"' in dashboard
    assert 'id="currentUpdatePasswordStatus"' in dashboard
    assert 'const updateUsername = getConfigTextValue("updateUsername").trim();' in dashboard
    assert 'const updatePassword = getConfigTextValue("updatePassword");' in dashboard
    assert 'payload.update_username = updateUsername;' in dashboard
    assert 'payload.update_password = updatePassword;' in dashboard
    assert '"updateUsername"' in dashboard
    assert '"updatePassword"' in dashboard

def test_nav_buttons_scroll_to_content_sections_not_nav_buttons():
    dashboard = _dashboard_html()

    assert "document.querySelector('section.content-card[data-view=\"' + normalized + '\"]')" in dashboard
    assert "document.querySelector('[data-view=\"' + normalized + '\"]')" not in dashboard

def test_config_form_uses_lazy_tabs_with_preserved_draft_state():
    dashboard = _dashboard_html()

    assert 'id="configTabs"' in dashboard
    assert 'data-config-tab="machine"' in dashboard
    assert 'data-config-tab="startup"' in dashboard
    assert 'data-config-tab="credentials"' in dashboard
    assert 'data-config-tab="timing"' in dashboard
    assert 'id="configTabFields"' in dashboard
    assert 'activeConfigTab: "machine"' in dashboard
    assert 'configDraft: {}' in dashboard
    assert 'function captureConfigDraft()' in dashboard
    assert 'function renderConfigTab(tabName)' in dashboard
    assert 'function setConfigTab(tabName)' in dashboard
    assert 'CONFIG_TABS[selected]' in dashboard
    assert 'class="form-actions config-action-row"' in dashboard


def test_dashboard_collapses_repeated_refresh_failures():
    dashboard = _dashboard_html()

    assert "dashboardOffline: false" in dashboard
    assert 'if (!state.dashboardOffline)' in dashboard
    assert 'state.dashboardOffline = true;' in dashboard
    assert 'Dashboard connection restored.' in dashboard


def test_stop_cnc_accepts_manual_redirect_without_json_parse():
    dashboard = _dashboard_html()

    assert 'result.type === "opaqueredirect"' in dashboard
    assert 'result.status === 0' in dashboard
    assert 'CNC stop command accepted. Adapter recovery may take up to a minute.' in dashboard
    assert 'const data = contentType.includes("application/json") ? await result.json() : {};' in dashboard
