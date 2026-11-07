import pytest

from keypad_backup import __version__
from keypad_backup.cli import build_parser, choose_ports, rank_ports


class P:
    def __init__(self, device, description):
        self.device, self.description = device, description


PORTS = [
    P("COM5", "SAMSUNG Mobile USB Serial Port  (COM5)"),
    P("COM3", "Standard Serial over Bluetooth link (COM3)"),
    P("COM4", "Standard Serial over Bluetooth link (COM4)"),
    P("COM6", "SAMSUNG Mobile USB Modem"),
    P("COM9", "Arduino Uno"),
]


def test_rank_ports_prefers_modem_and_skips_bluetooth_and_other_devices():
    assert rank_ports(PORTS) == ["COM6", "COM5"]


def test_choose_ports_explicit_port_wins():
    assert choose_ports("COM12", ports=PORTS) == ["COM12"]


def test_choose_ports_auto():
    assert choose_ports(None, ports=PORTS) == ["COM6", "COM5"]


def test_choose_ports_asks_when_nothing_looks_like_a_phone():
    ports = [P("/dev/ttyUSB0", "USB Serial"), P("/dev/ttyS0", "ttyS0")]
    assert choose_ports(None, ports=ports, ask=lambda _: "1", say=lambda s: None) == ["/dev/ttyS0"]


def test_choose_ports_bad_answer_exits():
    ports = [P("/dev/ttyUSB0", "USB Serial")]
    with pytest.raises(SystemExit):
        choose_ports(None, ports=ports, ask=lambda _: "7", say=lambda s: None)


def test_no_ports_at_all_exits_with_help():
    with pytest.raises(SystemExit) as e:
        choose_ports(None, ports=[])
    assert "USB mode" in str(e.value)


def test_parser_defaults():
    args = build_parser().parse_args([])
    assert args.out == "phone_backup" and args.baud == 115200 and not args.full_log


def test_version_flag(capsys):
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--version"])
    assert __version__ in capsys.readouterr().out
