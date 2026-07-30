import pytest

from src.cnc.physical_button_monitor import PhysicalButtonService


@pytest.mark.asyncio
async def test_physical_run_starts_job_after_press_release(fake_client):
    service = PhysicalButtonService(fake_client, poll_interval_ms=50)
    fake_client._connected = True

    fake_client._physical_button_status = {"runInput": True, "pauseInput": False}
    await service.poll_once()
    fake_client._physical_button_status = {"runInput": False, "pauseInput": False}
    await service.poll_once()
    fake_client._physical_button_status = {"runInput": True, "pauseInput": False}
    update = await service.poll_once()

    assert update.actions == ("start_job",)
    assert fake_client.run_job_calls == 1

@pytest.mark.asyncio
async def test_physical_run_is_ignored_until_cnc_is_connected(fake_client):
    service = PhysicalButtonService(fake_client, poll_interval_ms=50)
    fake_client._connected = False

    fake_client._physical_button_status = {"runInput": False, "pauseInput": False}
    await service.poll_once()
    fake_client._physical_button_status = {"runInput": True, "pauseInput": False}
    update = await service.poll_once()

    assert update.actions == ()
    assert fake_client.run_job_calls == 0

@pytest.mark.asyncio
async def test_physical_run_is_ignored_in_error_state(fake_client):
    service = PhysicalButtonService(fake_client, poll_interval_ms=50)
    fake_client._connected = True
    fake_client._state = 3

    fake_client._physical_button_status = {"runInput": False, "pauseInput": False}
    await service.poll_once()
    fake_client._physical_button_status = {"runInput": True, "pauseInput": False}
    await service.poll_once()

    assert fake_client.run_job_calls == 0


@pytest.mark.asyncio
async def test_physical_pause_pauses_only_running_job(fake_client):
    service = PhysicalButtonService(fake_client, poll_interval_ms=50)
    fake_client._connected = True
    fake_client._state = 6
    fake_client._physical_button_status = {"runInput": True, "pauseInput": True}

    update = await service.poll_once()

    assert update.actions == ("pause_job",)
    assert fake_client.pause_job_calls == 1


@pytest.mark.asyncio
async def test_physical_pause_is_ignored_when_not_running(fake_client):
    service = PhysicalButtonService(fake_client, poll_interval_ms=50)
    fake_client._connected = True
    fake_client._state = 2
    fake_client._physical_button_status = {"runInput": True, "pauseInput": True}

    await service.poll_once()

    assert fake_client.pause_job_calls == 0
