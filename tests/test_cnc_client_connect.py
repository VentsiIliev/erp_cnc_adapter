from unittest.mock import MagicMock


def test_connect_does_not_reset_powerup_during_handshake():
    from src.cnc.cnc_client import CNC_RC_ALREADY_CONNECTED, CncClient

    client = CncClient.__new__(CncClient)
    client._settings = MagicMock(ini_path=r"C:\CNC4.03\cnc.ini")
    client._connected = False
    client._dll = MagicMock()
    client._dll.CncConnectServer.return_value = CNC_RC_ALREADY_CONNECTED
    client._dll.CncGetState.return_value = 0

    assert client.connect() == CNC_RC_ALREADY_CONNECTED
    assert client.is_connected is True
    client._dll.CncReset.assert_not_called()
