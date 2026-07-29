import pytest


@pytest.mark.asyncio
async def test_position_endpoint_returns_work_and_machine_coordinates(client):
    response = await client.get("/api/cnc/position")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "status": 0,
        "message": "CNC position read successfully",
        "work": {"x": 1.25, "y": 2.5, "z": -3.75, "a": 0.0, "b": 0.0, "c": 0.0},
        "machine": {"x": 10.0, "y": 20.0, "z": -30.0, "a": 0.0, "b": 0.0, "c": 0.0},
    }




@pytest.mark.asyncio
async def test_physical_buttons_endpoint_returns_cnc_input_status(client, fake_client):
    fake_client._physical_button_status = {
        "runInput": True,
        "pauseInput": False,
        "runRaw": 0,
        "pauseRaw": 1,
        "runLogical": 0,
        "pauseLogical": 0,
        "feedHoldActive": True,
        "safetyInputValue": 0,
        "motionEnabled": True,
    }

    response = await client.get("/api/cnc/physical-buttons")

    assert response.status_code == 200
    assert response.json() == {
        "status": 0,
        "message": "CNC physical button status read successfully",
        "runInput": True,
        "pauseInput": False,
        "runRaw": 0,
        "pauseRaw": 1,
        "runLogical": 0,
        "pauseLogical": 0,
        "feedHoldActive": True,
        "safetyInputValue": 0,
        "motionEnabled": True,
    }


@pytest.mark.asyncio
async def test_reset_endpoint_calls_cnc_client(client, fake_client):
    response = await client.post("/api/cnc/reset")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == 0
    assert body["message"] == "CNC DLL accepted reset command: CncReset returned 0"
    assert body["command"] == "reset"
    assert body["dryRun"] is False
    assert fake_client.reset_calls == 1


@pytest.mark.asyncio
async def test_reset_endpoint_returns_cnc_error(client, fake_client):
    fake_client._reset_rc = 14

    response = await client.post("/api/cnc/reset")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == 14
    assert "Execution error" in body["message"]


@pytest.mark.asyncio
async def test_pause_job_endpoint_returns_immediately_when_no_job_running(client, fake_client):
    fake_client._state = 2

    response = await client.post("/api/cnc/job/pause")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == 0
    assert "Pause hold idle" in body["message"]
    assert fake_client.pause_job_calls == 0


@pytest.mark.asyncio
async def test_pause_job_endpoint_does_not_pause_single_line_homing(client, fake_client):
    fake_client._state = 7

    response = await client.post("/api/cnc/job/pause")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == 0
    assert "Pause hold idle" in body["message"]
    assert "state 7" in body["message"]
    assert fake_client.pause_job_calls == 0


@pytest.mark.asyncio
async def test_pause_job_endpoint_returns_immediately_when_already_paused(client, fake_client):
    fake_client._state = 12

    response = await client.post("/api/cnc/job/pause")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == 0
    assert "already paused" in body["message"]
    assert fake_client.pause_job_calls == 0


@pytest.mark.asyncio
async def test_pause_job_endpoint_calls_cnc_client(client, fake_client):
    fake_client._state = 6

    response = await client.post("/api/cnc/job/pause")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == 0
    assert body["message"] == (
        "Pause hold active: running job was paused by the jog pad hold. "
        "Press Proceed to release the jog pad hold before continuing."
    )
    assert body["command"] == "pause_job"
    assert body["dryRun"] is False
    assert fake_client.pause_job_calls == 1


@pytest.mark.asyncio
async def test_pause_job_endpoint_returns_cnc_error(client, fake_client):
    fake_client._state = 6
    fake_client._pause_job_rc = 10

    response = await client.post("/api/cnc/job/pause")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == 10
    assert "Invalid state" in body["message"]

@pytest.mark.asyncio
async def test_jog_endpoint_calls_cnc_client(client, fake_client):
    response = await client.post(
        "/api/cnc/jog",
        json={
            "axis": "x",
            "direction": 1,
            "step": 2.5,
            "velocity_factor": 0.5,
            "continuous": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "status": 0,
        "message": "CNC DLL accepted jog command: CncStartJog2 returned 0",
        "command": "jog",
        "dryRun": False,
        "axis": "X",
        "direction": 1,
        "step": 2.5,
        "position": None,
        "velocityFactor": 0.5,
        "continuous": False,
    }
    assert fake_client.jog_commands == [
        {
            "axis": "X",
            "direction": 1,
            "step": 2.5,
            "velocity_factor": 0.5,
            "continuous": False,
        }
    ]



@pytest.mark.asyncio
async def test_jog_endpoint_does_not_block_on_motion_enabled_false(client, fake_client):
    fake_client._motion_enabled = False

    response = await client.post(
        "/api/cnc/jog",
        json={"axis": "X", "direction": 1, "step": 1.0, "velocity_factor": 0.1, "continuous": False},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == 0
    assert fake_client.jog_commands == [
        {
            "axis": "X",
            "direction": 1,
            "step": 1.0,
            "velocity_factor": 0.1,
            "continuous": False,
        }
    ]

@pytest.mark.asyncio
async def test_jog_endpoint_returns_cnc_error(client, fake_client):
    fake_client._start_jog_rc = 10

    response = await client.post(
        "/api/cnc/jog",
        json={"axis": "Y", "direction": -1, "step": 1.0, "velocity_factor": 0.25, "continuous": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == 10
    assert body["dryRun"] is False
    assert "Invalid state" in body["message"]


@pytest.mark.asyncio
async def test_jog_endpoint_rejects_unknown_axis(client):
    response = await client.post(
        "/api/cnc/jog",
        json={"axis": "Q", "direction": 1},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_stop_jog_endpoint_calls_cnc_client(client, fake_client):
    response = await client.post("/api/cnc/jog/stop")

    assert response.status_code == 200
    body = response.json()
    assert body["command"] == "jog_stop"
    assert body["dryRun"] is False
    assert body["axis"] is None
    assert body["message"] == "CNC DLL accepted jog stop command: CncStopJog returned 0"
    assert fake_client.stop_jog_commands == [None]


@pytest.mark.asyncio
async def test_move_endpoint_calls_cnc_client(client, fake_client):
    response = await client.post(
        "/api/cnc/move",
        json={"axis": "z", "position": -12.75, "velocity_factor": 0.2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["command"] == "move"
    assert body["dryRun"] is False
    assert body["axis"] == "Z"
    assert body["position"] == -12.75
    assert body["velocityFactor"] == 0.2
    assert body["message"] == "CNC DLL accepted move command: CncMoveTo returned 0"
    assert fake_client.move_commands == [
        {"axis": "Z", "position": -12.75, "velocity_factor": 0.2}
    ]

@pytest.mark.asyncio
async def test_zero_endpoint_calls_cnc_client(client, fake_client):
    response = await client.post("/api/cnc/zero", json={"axis": "x"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == 0
    assert body["command"] == "zero"
    assert body["dryRun"] is False
    assert body["axis"] == "X"
    assert body["message"] == "CNC DLL zeroed work axis: G10 L20 and CncStoreIniFile returned 0"
    assert fake_client.zero_commands == ["X"]


@pytest.mark.asyncio
async def test_zero_endpoint_returns_cnc_error(client, fake_client):
    fake_client._zero_work_axis_rc = 14

    response = await client.post("/api/cnc/zero", json={"axis": "Z"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == 14
    assert "Execution error" in body["message"]


@pytest.mark.asyncio
async def test_zero_endpoint_rejects_unknown_axis(client):
    response = await client.post("/api/cnc/zero", json={"axis": "Q"})

    assert response.status_code == 422

@pytest.mark.asyncio
async def test_set_work_coordinate_endpoint_calls_cnc_client(client, fake_client):
    response = await client.post("/api/cnc/work-coordinate", json={"axis": "y", "value": 12.345})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == 0
    assert body["command"] == "set_work_coordinate"
    assert body["dryRun"] is False
    assert body["axis"] == "Y"
    assert body["position"] == 12.345
    assert body["message"] == "CNC DLL set work coordinate: G92 and CncStoreIniFile returned 0"
    assert fake_client.set_work_coordinate_commands == [{"axis": "Y", "value": 12.345}]


@pytest.mark.asyncio
async def test_set_work_coordinate_endpoint_returns_cnc_error(client, fake_client):
    fake_client._set_work_coordinate_rc = 14

    response = await client.post("/api/cnc/work-coordinate", json={"axis": "Z", "value": 0})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == 14
    assert "Execution error" in body["message"]


@pytest.mark.asyncio
async def test_set_work_coordinate_endpoint_rejects_unknown_axis(client):
    response = await client.post("/api/cnc/work-coordinate", json={"axis": "Q", "value": 0})

    assert response.status_code == 422

@pytest.mark.asyncio
async def test_homed_endpoint_returns_all_axes_homed(client, fake_client):
    fake_client._all_axes_homed = True

    response = await client.get("/api/cnc/homed")

    assert response.status_code == 200
    assert response.json() == {
        "status": 0,
        "message": "All axes are homed",
        "allAxesHomed": True,
    }


@pytest.mark.asyncio
async def test_homed_endpoint_returns_not_all_axes_homed(client, fake_client):
    fake_client._all_axes_homed = False

    response = await client.get("/api/cnc/homed")

    assert response.status_code == 200
    assert response.json() == {
        "status": 0,
        "message": "Not all axes are homed",
        "allAxesHomed": False,
    }

@pytest.mark.asyncio
async def test_home_endpoint_calls_home_all_macro(client, fake_client):
    response = await client.post("/api/cnc/home")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == 0
    assert body["message"] == "CNC home_all macro completed: gosub home_all returned 0"
    assert body["command"] == "home"
    assert body["dryRun"] is False
    assert fake_client.home_all_axes_calls == 1


@pytest.mark.asyncio
async def test_home_endpoint_returns_cnc_error(client, fake_client):
    fake_client._home_all_axes_rc = 14

    response = await client.post("/api/cnc/home")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == 14
    assert "Execution error" in body["message"]

@pytest.mark.asyncio
async def test_home_endpoint_prefers_eding_cnc_message(client, fake_client):
    fake_client._home_all_axes_rc = -1
    fake_client._last_cnc_message = "No Job loaded"

    response = await client.post("/api/cnc/home")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == -1
    assert body["message"] == "No Job loaded"

@pytest.mark.asyncio
async def test_home_endpoint_prefers_eding_cnc_message_on_success(client, fake_client):
    fake_client._home_all_axes_rc = 0
    fake_client._last_cnc_message = "Home complete"

    response = await client.post("/api/cnc/home")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == 0
    assert body["message"] == "Home complete"

@pytest.mark.asyncio
async def test_jog_endpoint_prefers_eding_cnc_message(client, fake_client):
    fake_client._start_jog_rc = 10
    fake_client._last_cnc_message = "drives not enabled"

    response = await client.post(
        "/api/cnc/jog",
        json={"axis": "X", "direction": 1, "step": 1.0, "velocity_factor": 0.1, "continuous": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == 10
    assert body["message"] == "drives not enabled"

@pytest.mark.asyncio
async def test_clear_cnc_messages_endpoint_calls_cnc_client(client, fake_client):
    fake_client._last_cnc_message = "old message"

    response = await client.post("/api/cnc/messages/clear")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == 0
    assert body["message"] == "CNC message FIFO cleared"
    assert body["command"] == "clear_messages"
    assert body["dryRun"] is False
    assert fake_client.clear_cnc_messages_calls == 1
    assert fake_client._last_cnc_message is None
