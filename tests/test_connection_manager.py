"""Tests for ConnectionManager — retry logic, heartbeat, and state transitions."""

import asyncio

import pytest

from src.cnc.connection_manager import ConnectionManager


class TestConnectionManagerInit:

    def test_initial_state(self, connection_manager):
        assert connection_manager.state == "disconnected"
        assert connection_manager.connected is False
        assert connection_manager.retry_count == 0
        assert connection_manager.last_error is None
        assert connection_manager.uptime_seconds is None


class TestConnectionManagerRetry:

    async def test_connects_when_server_alive(self, fake_client, settings):
        """Manager should connect on first retry when server is available."""
        fake_client._server_process_alive = True
        fake_client._connect_rc = 0

        mgr = ConnectionManager(fake_client, settings)
        mgr.start()

        # Give it time to run one retry cycle
        await asyncio.sleep(0.3)

        assert mgr.state == "connected"
        assert mgr.connected is True
        assert fake_client.is_connected is True
        assert mgr.retry_count == 0

        await mgr.stop()

    async def test_cnc_not_running_state(self, fake_client, settings):
        """When CncServer.exe is not found, state should be cnc_not_running."""
        fake_client._server_process_alive = False
        settings.cnc_retry_interval = 0.1

        mgr = ConnectionManager(fake_client, settings)
        mgr.start()

        await asyncio.sleep(0.3)

        assert mgr.state == "cnc_not_running"
        assert mgr.last_error == "CncServer.exe not found"

        await mgr.stop()

    async def test_retries_on_connect_failure(self, fake_client, settings):
        """When connect() returns an error code, manager should retry."""
        fake_client._server_process_alive = True
        fake_client._connect_rc = 99  # unknown error
        settings.cnc_retry_interval = 0.1

        mgr = ConnectionManager(fake_client, settings)
        mgr.start()

        await asyncio.sleep(0.5)

        assert mgr.state == "retrying"
        assert mgr.retry_count > 0
        assert mgr.last_error is not None

        await mgr.stop()

    async def test_already_connected_counts_as_success(self, fake_client, settings):
        """RC codes 6 (ALREADY_RUNS) and 7 (ALREADY_CONNECTED) are OK."""
        fake_client._server_process_alive = True
        fake_client._connect_rc = 7  # CNC_RC_ALREADY_CONNECTED

        mgr = ConnectionManager(fake_client, settings)
        mgr.start()

        await asyncio.sleep(0.3)

        assert mgr.connected is True

        await mgr.stop()


class TestConnectionManagerHeartbeat:

    async def test_heartbeat_detects_disconnect(self, fake_client, settings):
        """When heartbeat fails, manager should drop to retrying/cnc_not_running."""
        fake_client._server_process_alive = True
        fake_client._connect_rc = 0
        settings.cnc_health_interval = 0.1
        settings.cnc_retry_interval = 0.1

        mgr = ConnectionManager(fake_client, settings)
        mgr.start()

        # Wait for connection
        await asyncio.sleep(0.3)
        assert mgr.connected is True

        # Simulate server disappearing
        fake_client._server_connected = False
        fake_client._server_process_alive = False

        await asyncio.sleep(0.5)

        assert mgr.state in ("cnc_not_running", "retrying")

        await mgr.stop()


class TestConnectionManagerLifecycle:

    async def test_stop_sets_disconnected(self, fake_client, settings):
        """After stop(), state should be disconnected."""
        mgr = ConnectionManager(fake_client, settings)
        mgr.start()
        await asyncio.sleep(0.1)

        await mgr.stop()

        assert mgr.state == "disconnected"

    async def test_start_is_idempotent(self, fake_client, settings):
        """Calling start() twice should not create duplicate tasks."""
        mgr = ConnectionManager(fake_client, settings)
        mgr.start()
        task1 = mgr._task
        mgr.start()
        task2 = mgr._task
        assert task1 is task2

        await mgr.stop()

    async def test_stop_without_start(self, connection_manager):
        """Stopping a manager that was never started should be a no-op."""
        await connection_manager.stop()
        assert connection_manager.state == "disconnected"

    async def test_uptime_tracks_after_connect(self, fake_client, settings):
        """uptime_seconds should return a value once connected."""
        fake_client._server_process_alive = True
        fake_client._connect_rc = 0

        mgr = ConnectionManager(fake_client, settings)
        mgr.start()

        await asyncio.sleep(0.3)

        assert mgr.connected is True
        assert mgr.uptime_seconds is not None
        assert mgr.uptime_seconds >= 0

        await mgr.stop()

    async def test_nudge_wakes_retry_immediately(self, fake_client, settings):
        """nudge() should cut the retry sleep short and connect faster."""
        fake_client._server_process_alive = False
        settings.cnc_retry_interval = 60  # very long — would timeout without nudge

        mgr = ConnectionManager(fake_client, settings)
        mgr.start()

        await asyncio.sleep(0.1)
        assert mgr.state == "cnc_not_running"

        # Now make server available and nudge
        fake_client._server_process_alive = True
        fake_client._connect_rc = 0
        mgr.nudge()

        await asyncio.sleep(0.5)

        assert mgr.connected is True

        await mgr.stop()