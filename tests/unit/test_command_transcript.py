from benchmark.session.models import CommandType
from benchmark.session.transcript import build_saved_command_logs


def test_build_saved_command_logs_includes_config_and_read():
    entries = [
        ("R1", "ip addr add 10.1.1.1/30 dev eth1", CommandType.CONFIG, True),
        ("R1", "ping -c 3 10.1.1.2", CommandType.READ, True),
        ("R2", "show ip route", CommandType.READ, False),
    ]
    transcript, execution_log = build_saved_command_logs(entries)

    assert len(transcript) == 3
    assert transcript[0].command_type == "config"
    assert transcript[1].command_type == "read"
    assert transcript[2].success is False

    assert execution_log[0] == "R1 | config | ip addr add 10.1.1.1/30 dev eth1 | ok"
    assert execution_log[1] == "R1 | read | ping -c 3 10.1.1.2 | ok"
    assert execution_log[2] == "R2 | read | show ip route | fail"
