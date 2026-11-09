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


def test_parser_backup_subcommand():
    args = build_parser().parse_args(["backup"])
    assert args.command == "backup"
    assert args.out == "phone_backup"
    assert args.baud == 115200


def test_parser_backup_with_flags():
    args = build_parser().parse_args(["backup", "-p", "COM7", "-o", "my_backup", "--baud", "9600", "--full-log"])
    assert args.command == "backup"
    assert args.port == "COM7"
    assert args.out == "my_backup"
    assert args.baud == 9600
    assert args.full_log is True


def test_parser_list_ports_subcommands():
    args1 = build_parser().parse_args(["list-ports"])
    assert args1.command == "list-ports"

    args2 = build_parser().parse_args(["ports"])
    assert args2.command == "ports"


def test_main_list_ports_subcommand(monkeypatch, capsys):
    from keypad_backup import cli
    monkeypatch.setattr(cli.list_ports, "comports", lambda: [P("COM1", "Test Port")])
    assert cli.main(["list-ports"]) == 0
    out = capsys.readouterr().out
    assert "COM1\tTest Port" in out


def test_main_ports_subcommand(monkeypatch, capsys):
    from keypad_backup import cli
    monkeypatch.setattr(cli.list_ports, "comports", lambda: [P("COM2", "Test Port 2")])
    assert cli.main(["ports"]) == 0
    out = capsys.readouterr().out
    assert "COM2\tTest Port 2" in out
