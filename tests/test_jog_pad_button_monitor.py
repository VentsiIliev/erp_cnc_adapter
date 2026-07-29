from src.jog_pad.button_monitor import PhysicalButtonMonitor


def test_run_indicator_confirms_after_press_release_cycle():
    monitor = PhysicalButtonMonitor()
    released_payload = {"runInput": True, "pauseInput": False}
    pressed_payload = {"runInput": False, "pauseInput": False}

    assert monitor.update(released_payload).indicators["runInput"] is False
    assert monitor.update(pressed_payload).indicators["runInput"] is False

    update = monitor.update(released_payload)

    assert update.indicators["runInput"] is True
    assert update.actions == (PhysicalButtonMonitor.ACTION_START_JOB,)


def test_reset_clears_run_confirmation():
    monitor = PhysicalButtonMonitor()
    monitor.update({"runInput": False, "pauseInput": False})
    assert monitor.update({"runInput": True, "pauseInput": False}).indicators["runInput"] is True

    monitor.reset()

    assert monitor.update({"runInput": True, "pauseInput": False}).indicators["runInput"] is False


def test_pause_indicator_uses_payload_state_directly_and_dispatches_once_per_press():
    monitor = PhysicalButtonMonitor()

    update = monitor.update({"runInput": True, "pauseInput": True})

    assert update.indicators["pauseInput"] is True
    assert update.actions == (PhysicalButtonMonitor.ACTION_PAUSE_JOB,)

    held_update = monitor.update({"runInput": True, "pauseInput": True})

    assert held_update.indicators["pauseInput"] is True
    assert held_update.actions == ()
    assert monitor.update({"runInput": True, "pauseInput": False}).indicators["pauseInput"] is False
