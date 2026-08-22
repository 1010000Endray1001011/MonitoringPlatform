from apps.common.tasks import ping


def test_ping_task_returns_pong():
    result = ping.apply()

    assert result.result == "pong"
