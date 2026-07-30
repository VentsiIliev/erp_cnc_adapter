from unittest.mock import MagicMock

import pytest

from src.cnc.message_monitor import CncMessageService


@pytest.mark.asyncio
async def test_poll_once_stores_recent_messages():
    client = MagicMock()
    client.poll_cnc_messages.return_value = ["Home Z", "Home complete"]
    service = CncMessageService(client, poll_interval_ms=100, max_messages=5)

    captured = await service.poll_once()

    assert [message.text for message in captured] == ["Home Z", "Home complete"]
    assert [message["text"] for message in service.recent_messages(limit=10)] == ["Home Z", "Home complete"]


@pytest.mark.asyncio
async def test_poll_once_limits_recent_messages():
    client = MagicMock()
    client.poll_cnc_messages.return_value = ["one", "two", "three"]
    service = CncMessageService(client, poll_interval_ms=100, max_messages=2)

    await service.poll_once()

    assert [message["text"] for message in service.recent_messages(limit=10)] == ["two", "three"]


def test_clear_discards_recent_messages():
    service = CncMessageService(MagicMock(), poll_interval_ms=100, max_messages=5)
    service._messages.append(MagicMock(as_dict=MagicMock(return_value={"timestampUtc": "now", "text": "old"})))

    service.clear()

    assert service.recent_messages() == []