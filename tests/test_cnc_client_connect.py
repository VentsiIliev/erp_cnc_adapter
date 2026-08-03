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


def test_start_jog_calls_cnc_start_jog2_with_signed_step():
    from src.cnc.cnc_client import CncClient

    client = CncClient.__new__(CncClient)
    client._dll = MagicMock()
    client._dll.CncStartJog2.return_value = 0

    assert client.start_jog("Y", -1, 2.5, 0.5, True) == 0

    axis, step, velocity, continuous = client._dll.CncStartJog2.call_args.args
    assert axis.value == 1
    assert step.value == -2.5
    assert velocity.value == 0.5
    assert continuous.value == 1


def test_stop_jog_without_axis_stops_all_cartesian_axes():
    from src.cnc.cnc_client import CncClient

    client = CncClient.__new__(CncClient)
    client._dll = MagicMock()
    client._dll.CncStopJog.return_value = 0

    assert client.stop_jog() == 0

    assert [call.args[0].value for call in client._dll.CncStopJog.call_args_list] == [0, 1, 2, 3, 4, 5]


def test_start_jog_failure_captures_delayed_fifo_message():
    import ctypes
    from cncapi.python.cncstructs import CNC_LOG_MESSAGE
    from src.cnc.cnc_client import CncClient

    client = CncClient.__new__(CncClient)
    client._last_cnc_message = None
    client._captured_cnc_messages = []
    client._dll = MagicMock()
    client._dll.CncStartJog2.return_value = 10

    reads = iter([None, b"Limit switch active", None, None])

    def fake_fifo_get(message_ref):
        next_message = next(reads, None)
        if next_message is None:
            return 1
        message = ctypes.cast(message_ref, ctypes.POINTER(CNC_LOG_MESSAGE)).contents
        message.text = next_message
        return 0

    client._dll.CncLogFifoGet.side_effect = fake_fifo_get

    assert client.start_jog("X", 1, 1.0, 0.1, True) == 10
    assert client.poll_cnc_messages() == ["Limit switch active"]
    assert client.get_last_cnc_message() == "Limit switch active"


def test_move_to_calls_cnc_move_to_for_single_axis():
    from src.cnc.cnc_client import CncClient

    client = CncClient.__new__(CncClient)
    client._dll = MagicMock()
    client._dll.CncMoveTo.return_value = 0

    assert client.move_to("Z", -12.75, 0.2) == 0

    pos, move, velocity = client._dll.CncMoveTo.call_args.args
    assert pos.z == -12.75
    assert move.z == 1
    assert move.x == 0
    assert velocity.value == 0.2


def test_move_to_captures_delayed_fifo_message():
    import ctypes
    from cncapi.python.cncstructs import CNC_LOG_MESSAGE
    from src.cnc.cnc_client import CncClient

    client = CncClient.__new__(CncClient)
    client._last_cnc_message = None
    client._captured_cnc_messages = []
    client._dll = MagicMock()
    client._dll.CncMoveTo.return_value = 0

    reads = iter([None, b"Move accepted", None, None])

    def fake_fifo_get(message_ref):
        next_message = next(reads, None)
        if next_message is None:
            return 1
        message = ctypes.cast(message_ref, ctypes.POINTER(CNC_LOG_MESSAGE)).contents
        message.text = next_message
        return 0

    client._dll.CncLogFifoGet.side_effect = fake_fifo_get

    assert client.move_to("Z", -12.75, 0.2) == 0
    assert client.poll_cnc_messages() == ["Move accepted"]
    assert client.get_last_cnc_message() == "Move accepted"


def test_get_positions_reads_work_and_machine_coordinates():
    from cncapi.python.cncstructs import CNC_CART_DOUBLE
    from src.cnc.cnc_client import CncClient

    work = CNC_CART_DOUBLE()
    work.x = 1.0
    work.y = 2.0
    work.z = 3.0
    machine = CNC_CART_DOUBLE()
    machine.x = 10.0
    machine.y = 20.0
    machine.z = 30.0

    client = CncClient.__new__(CncClient)
    client._dll = MagicMock()
    client._dll.CncGetWorkPosition.return_value = work
    client._dll.CncGetMachinePosition.return_value = machine

    assert client.get_positions() == {
        "work": {"x": 1.0, "y": 2.0, "z": 3.0, "a": 0.0, "b": 0.0, "c": 0.0},
        "machine": {"x": 10.0, "y": 20.0, "z": 30.0, "a": 0.0, "b": 0.0, "c": 0.0},
    }


def test_zero_work_axis_runs_g10_l20_for_active_coordinate_system():
    from src.cnc.cnc_client import CncClient

    status = MagicMock()
    status.activeOffsetAndPlane.currentG5X = 1  # G55, converted to G10 P2

    client = CncClient.__new__(CncClient)
    client._dll = MagicMock()
    client._dll.CncGetRunningStatus.return_value.contents = status
    client._dll.CncRunSingleLine.return_value = 0
    client._dll.CncWaitSingleLine.return_value = 0
    client._dll.CncStoreIniFile.return_value = 0

    assert client.zero_work_axis("x") == 0

    client._dll.CncRunSingleLine.assert_called_once_with(b"G10 L20 P2 X0")
    client._dll.CncWaitSingleLine.assert_called_once_with(None, None)
    save_fixtures = client._dll.CncStoreIniFile.call_args.args[0]
    assert save_fixtures.value == 1


def test_zero_work_axis_captures_delayed_fifo_message():
    import ctypes
    from cncapi.python.cncstructs import CNC_LOG_MESSAGE
    from src.cnc.cnc_client import CncClient

    status = MagicMock()
    status.activeOffsetAndPlane.currentG5X = 0

    client = CncClient.__new__(CncClient)
    client._last_cnc_message = None
    client._captured_cnc_messages = []
    client._dll = MagicMock()
    client._dll.CncGetRunningStatus.return_value.contents = status
    client._dll.CncRunSingleLine.return_value = 0
    client._dll.CncWaitSingleLine.return_value = 0
    client._dll.CncStoreIniFile.return_value = 0

    reads = iter([None, b"Zero X complete", None, None])

    def fake_fifo_get(message_ref):
        next_message = next(reads, None)
        if next_message is None:
            return 1
        message = ctypes.cast(message_ref, ctypes.POINTER(CNC_LOG_MESSAGE)).contents
        message.text = next_message
        return 0

    client._dll.CncLogFifoGet.side_effect = fake_fifo_get

    assert client.zero_work_axis("x") == 0
    assert client.poll_cnc_messages() == ["Zero X complete"]
    assert client.get_last_cnc_message() == "Zero X complete"


def test_set_work_coordinate_runs_g92_single_line_and_saves_ini():
    from src.cnc.cnc_client import CncClient

    client = CncClient.__new__(CncClient)
    client._dll = MagicMock()
    client._dll.CncRunSingleLine.return_value = 0
    client._dll.CncWaitSingleLine.return_value = 0
    client._dll.CncStoreIniFile.return_value = 0

    assert client.set_work_coordinate("z", -1.25) == 0

    client._dll.CncRunSingleLine.assert_called_once_with(b"G92 Z-1.25")
    client._dll.CncWaitSingleLine.assert_called_once_with(None, None)
    save_fixtures = client._dll.CncStoreIniFile.call_args.args[0]
    assert save_fixtures.value == 1


def test_get_all_axes_homed_reads_cnc_dll_status():
    from src.cnc.cnc_client import CncClient

    client = CncClient.__new__(CncClient)
    client._dll = MagicMock()
    client._dll.CncGetAllAxesHomed.return_value = 1

    assert client.get_all_axes_homed() is True

    client._dll.CncGetAllAxesHomed.return_value = 0
    assert client.get_all_axes_homed() is False


def test_home_all_axes_gui_sequence_sends_gui_home_action():
    from src.cnc.cnc_client import CncClient

    client = CncClient.__new__(CncClient)
    client._dll = MagicMock()
    client._dll.CncSendToGUI.return_value = 0
    client._wait_for_cnc_messages = MagicMock(return_value=False)

    assert client.home_all_axes_gui_sequence() == 0

    action, p1, p2 = client._dll.CncSendToGUI.call_args.args
    assert action.value == 37
    assert p1.value == 0
    assert p2.value == 0
    client._dll.CncRunSingleLine.assert_not_called()


def test_home_all_axes_sequence_runs_home_all_macro():
    from src.cnc.cnc_client import CncClient

    client = CncClient.__new__(CncClient)
    client._dll = MagicMock()
    client._dll.CncRunSingleLine.return_value = 0
    client._dll.CncWaitSingleLine.return_value = 0
    client._wait_for_cnc_messages = MagicMock(return_value=False)

    assert client.home_all_axes_sequence() == 0

    client._dll.CncRunSingleLine.assert_called_once_with(b"gosub home_all")
    client._dll.CncWaitSingleLine.assert_called_once_with(None, None)
    client._dll.CncSendToGUI.assert_not_called()


def test_home_all_axes_sequence_returns_gosub_rejection_without_fallback():
    from src.cnc.cnc_client import CncClient

    client = CncClient.__new__(CncClient)
    client._dll = MagicMock()
    client._dll.CncRunSingleLine.return_value = -1

    assert client.home_all_axes_sequence() == -1

    client._dll.CncRunSingleLine.assert_called_once_with(b"gosub home_all")
    client._dll.CncWaitSingleLine.assert_not_called()
    client._dll.CncSendToGUI.assert_not_called()


def test_home_all_axes_sequence_captures_fifo_message_on_rejection():
    import ctypes
    from cncapi.python.cncstructs import CNC_LOG_MESSAGE
    from src.cnc.cnc_client import CncClient

    client = CncClient.__new__(CncClient)
    client._last_cnc_message = None
    client._captured_cnc_messages = []
    client._dll = MagicMock()
    client._dll.CncRunSingleLine.return_value = -1

    reads = iter([None, b"No Job loaded", None, None])

    def fake_fifo_get(message_ref):
        next_message = next(reads, None)
        if next_message is None:
            return 1
        message = ctypes.cast(message_ref, ctypes.POINTER(CNC_LOG_MESSAGE)).contents
        message.text = next_message
        return 0

    client._dll.CncLogFifoGet.side_effect = fake_fifo_get

    assert client.home_all_axes_sequence() == -1
    assert client.poll_cnc_messages() == ["No Job loaded"]
    assert client.get_last_cnc_message() == "No Job loaded"
    client._dll.CncWaitSingleLine.assert_not_called()
    client._dll.CncSendToGUI.assert_not_called()


def test_home_all_axes_sequence_waits_for_delayed_fifo_messages():
    import ctypes
    from cncapi.python.cncstructs import CNC_LOG_MESSAGE
    from src.cnc.cnc_client import CncClient

    client = CncClient.__new__(CncClient)
    client._last_cnc_message = None
    client._captured_cnc_messages = []
    client._dll = MagicMock()
    client._dll.CncRunSingleLine.return_value = 0
    client._dll.CncWaitSingleLine.return_value = 0

    messages = [None, b"HOME X", b"HOME Y", b"HOME Z", b"Home completed!"]

    def fake_fifo_get(message_ref):
        next_message = messages.pop(0) if messages else None
        if next_message is None:
            return 1
        message = ctypes.cast(message_ref, ctypes.POINTER(CNC_LOG_MESSAGE)).contents
        message.text = next_message
        return 0

    client._dll.CncLogFifoGet.side_effect = fake_fifo_get

    assert client.home_all_axes_sequence() == 0
    assert client.poll_cnc_messages() == ["HOME X", "HOME Y", "HOME Z", "Home completed!"]
    assert client.get_last_cnc_message() == "HOME X | HOME Y | HOME Z | Home completed!"


def test_wait_for_cnc_messages_collects_messages_until_fifo_is_quiet():
    import ctypes
    from cncapi.python.cncstructs import CNC_LOG_MESSAGE
    from src.cnc.cnc_client import CncClient

    client = CncClient.__new__(CncClient)
    client._last_cnc_message = None
    client._captured_cnc_messages = []
    client._dll = MagicMock()

    reads = iter([b"HOME X", None, b"HOME Y", None, b"HOME Z", None, b"Home completed!", None, None])

    def fake_fifo_get(message_ref):
        next_message = next(reads, None)
        if next_message is None:
            return 1
        message = ctypes.cast(message_ref, ctypes.POINTER(CNC_LOG_MESSAGE)).contents
        message.text = next_message
        return 0

    client._dll.CncLogFifoGet.side_effect = fake_fifo_get

    assert client._wait_for_cnc_messages("test", timeout_seconds=0.5, quiet_seconds=0.05) is True
    assert client.get_last_cnc_message() == "HOME X | HOME Y | HOME Z | Home completed!"


def test_pause_job_calls_cnc_pause_job():
    from src.cnc.cnc_client import CncClient

    client = CncClient.__new__(CncClient)
    client._dll = MagicMock()
    client._dll.CncPauseJob.return_value = 0

    assert client.pause_job() == 0
    client._dll.CncPauseJob.assert_called_once_with()


def test_run_job_uses_standard_run_when_not_paused():
    from src.cnc.cnc_client import CncClient

    client = CncClient.__new__(CncClient)
    client._dll = MagicMock()
    client._dll.CncGetState.return_value = 2
    client._dll.CncRunOrResumeJob.return_value = 0

    assert client.run_job() == 0

    client._dll.CncRunOrResumeJob.assert_called_once_with()
    client._dll.CncSyncFromPauseAndStartAutomatic.assert_not_called()


def test_run_job_syncs_from_pause_using_eding_ini_approach_feed(tmp_path):
    from cncapi.python.cncstructs import CNC_PAUSE_STS
    from src.cnc.cnc_client import CncClient

    ini_path = tmp_path / "cnc.ini"
    ini_path.write_text("[SAFETY]\napproachFeed = 123.400000\n", encoding="utf-8")

    pause_status = CNC_PAUSE_STS()
    pause_status.pausePositionValid = 1
    pause_status.pausePosition.z = 42.0
    pause_status.curPosInSync.z = 0

    client = CncClient.__new__(CncClient)
    client._settings = MagicMock(ini_path=str(ini_path))
    client._last_cnc_message = None
    client._captured_cnc_messages = []
    client._dll = MagicMock()
    client._dll.CncGetState.return_value = 12
    client._dll.CncGetPauseStatus.return_value.contents = pause_status
    client._dll.CncSyncFromPauseAndStartAutomatic.return_value = 0
    client._dll.CncLogFifoGet.return_value = 1
    client._wait_for_cnc_messages = MagicMock(return_value=False)

    assert client.run_job() == 0

    feed, callback, callback_param = client._dll.CncSyncFromPauseAndStartAutomatic.call_args.args
    assert feed.value == 123.4
    assert callback is None
    assert callback_param is None
    client._dll.CncRunOrResumeJob.assert_not_called()


def test_is_motion_enabled_reads_controller_status():
    from src.cnc.cnc_client import CncClient

    controller_status = MagicMock()
    controller_status.motionEnabled = 1
    client = CncClient.__new__(CncClient)
    client._dll = MagicMock()
    client._dll.CncGetControllerStatus.return_value.contents = controller_status

    assert client.is_motion_enabled() is True

    controller_status.motionEnabled = 0
    assert client.is_motion_enabled() is False


def test_reset_calls_cnc_reset():
    from src.cnc.cnc_client import CncClient

    client = CncClient.__new__(CncClient)
    client._dll = MagicMock()
    client._dll.CncReset.return_value = 0
    client._dll.CncLogFifoGet.return_value = 1

    assert client.reset() == 0
    client._dll.CncReset.assert_called_once_with()


def test_reset_captures_delayed_fifo_message():
    import ctypes
    from cncapi.python.cncstructs import CNC_LOG_MESSAGE
    from src.cnc.cnc_client import CncClient

    client = CncClient.__new__(CncClient)
    client._last_cnc_message = None
    client._captured_cnc_messages = []
    client._dll = MagicMock()
    client._dll.CncReset.return_value = 0

    reads = iter([None, b"Reset complete", None, None])

    def fake_fifo_get(message_ref):
        next_message = next(reads, None)
        if next_message is None:
            return 1
        message = ctypes.cast(message_ref, ctypes.POINTER(CNC_LOG_MESSAGE)).contents
        message.text = next_message
        return 0

    client._dll.CncLogFifoGet.side_effect = fake_fifo_get

    assert client.reset() == 0
    assert client.poll_cnc_messages() == ["Reset complete"]
    assert client.get_last_cnc_message() == "Reset complete"
