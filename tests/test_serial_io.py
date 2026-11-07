"""Tests the real Phone class against a fake serial port, plus the full CLI flow."""
import keypad_backup.cli as cli
import keypad_backup.phone as phone_mod
from keypad_backup.phone import Phone

from .fakes import FakePhone

REPLIES = {
    "AT": b"AT\r\n\r\nOK\r\n",
    "AT+CPBR=1,10": b'AT+CPBR=1,10\r\n+CPBR: 1,"+919812345678",145,"Mom"\r\n\r\nOK\r\n',
}


class FakeSerial:
    def __init__(self, port, baud, timeout=1):
        self.rx = b""
        self.closed = False

    @property
    def in_waiting(self):
        return len(self.rx)

    def reset_input_buffer(self):
        self.rx = b""

    def write(self, data):
        self.rx = REPLIES.get(data.decode().strip(), b"ERROR\r\n")

    def read(self, n):
        out, self.rx = self.rx[:n], self.rx[n:]
        return out

    def close(self):
        self.closed = True


def test_cmd_returns_reply_and_stops_at_ok_or_error(monkeypatch):
    monkeypatch.setattr(phone_mod.serial, "Serial", FakeSerial)
    with Phone("COM6") as ph:
        assert "OK" in ph.cmd("AT", timeout=2)
        assert "ERROR" in ph.cmd("AT+NOPE", timeout=2)
    assert ph.ser.closed


def test_log_hides_personal_data_by_default(monkeypatch, tmp_path):
    monkeypatch.setattr(phone_mod.serial, "Serial", FakeSerial)
    log = tmp_path / "raw_log.txt"
    with Phone("COM6", logfile=log) as ph:
        ph.cmd("AT+CPBR=1,10", timeout=2)
    text = log.read_text(encoding="utf-8")
    assert "Mom" not in text and "9812345678" not in text
    assert ">>> AT+CPBR=1,10" in text


def test_full_log_keeps_everything(monkeypatch, tmp_path):
    monkeypatch.setattr(phone_mod.serial, "Serial", FakeSerial)
    log = tmp_path / "raw_log.txt"
    with Phone("COM6", logfile=log, redact=False) as ph:
        ph.cmd("AT+CPBR=1,10", timeout=2)
    assert "Mom" in log.read_text(encoding="utf-8")


class _CtxFake(FakePhone):
    """FakePhone shaped like Phone(port, baud, logfile, redact=...) for main()."""
    contacts_to_use = {1: ("+919812345678", "Mom"), 2: ("12345", "Office")}
    silent = False

    def __init__(self, port, baud, logfile, redact=True):
        super().__init__(contacts=self.contacts_to_use, answers=not self.silent)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_main_end_to_end(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "Phone", _CtxFake)
    monkeypatch.setattr(cli, "choose_ports", lambda port_arg: ["COM6"])
    assert cli.main(["-o", str(tmp_path / "out")]) == 0
    out = tmp_path / "out"
    assert (out / "contacts.csv").read_text(encoding="utf-8-sig").count("\n") == 3  # header + 2 rows
    assert "Done: 2 contacts" in capsys.readouterr().out


def test_main_exit_code_1_when_nothing_read(monkeypatch, tmp_path):
    class Silent(_CtxFake):
        silent = True

    monkeypatch.setattr(cli, "Phone", Silent)
    monkeypatch.setattr(cli, "choose_ports", lambda port_arg: ["COM6", "COM5"])
    assert cli.main(["-o", str(tmp_path)]) == 1
    assert (tmp_path / "contacts.csv").exists()  # empty files are still written
