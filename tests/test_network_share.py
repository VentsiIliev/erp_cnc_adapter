"""Tests for explicit UNC share authentication."""

import subprocess
from unittest.mock import patch

from src.core.network_share import ensure_unc_share_authenticated, unc_share_root


def test_unc_share_root_extracts_server_and_share():
    assert unc_share_root(r"\\192.168.2.11\Production\CNC\Mills") == r"\\192.168.2.11\Production"


def test_unc_share_root_ignores_local_paths():
    assert unc_share_root(r"C:\CNC\Jobs") is None


@patch("src.core.network_share._hidden_startupinfo", return_value=None)
@patch("src.core.network_share.subprocess.run")
def test_ensure_unc_share_authenticated_uses_explicit_credentials(mock_run, _mock_startupinfo):
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="The command completed successfully.", stderr=""
    )

    result = ensure_unc_share_authenticated(
        r"\\192.168.2.11\Production\CNC\Mills",
        "CNC",
        "secret",
    )

    assert result.ok is True
    assert result.share == r"\\192.168.2.11\Production"
    mock_run.assert_called_once()
    command = mock_run.call_args.args[0]
    assert command == ["net", "use", r"\\192.168.2.11\Production", "/user:CNC", "secret", "/persistent:no"]


@patch("src.core.network_share._hidden_startupinfo", return_value=None)
@patch("src.core.network_share.subprocess.run")
def test_ensure_unc_share_authenticated_replaces_only_conflicting_share(mock_run, _mock_startupinfo):
    mock_run.side_effect = [
        subprocess.CompletedProcess(args=[], returncode=2, stdout="", stderr="System error 1219 has occurred."),
        subprocess.CompletedProcess(args=[], returncode=0, stdout="deleted", stderr=""),
        subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr=""),
    ]

    result = ensure_unc_share_authenticated(
        r"\\192.168.2.11\Production\CNC\Mills",
        "CNC",
        "secret",
    )

    assert result.ok is True
    assert mock_run.call_args_list[1].args[0] == ["net", "use", r"\\192.168.2.11\Production", "/delete", "/y"]
