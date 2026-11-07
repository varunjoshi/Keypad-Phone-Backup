"""Talking to the phone: sending AT commands and reading contacts / SMS."""
import re
import time

import serial

from .parsers import parse_cmgl, parse_cmgl_pdu, parse_cpbr

_SENSITIVE_CMD = re.compile(r"AT\+(CPBR|CPBF|CMGL|CMGR)=", re.I)
_SENSITIVE_HEADER = re.compile(r"\+(CPBR|CPBF|CMGL|CMGR):")
_ERROR_LINE = re.compile(r"^(ERROR|\+CM[ES] ERROR:.*)$")


def redact_reply(command, reply):
    """Hide personal data (names, numbers, message text) in a reply before it is logged."""
    cmd = command.strip()
    if not _SENSITIVE_CMD.match(cmd) or cmd.endswith("=?"):
        return reply
    out = []
    for line in reply.splitlines():
        s = line.strip()
        if not s or s == "OK" or _ERROR_LINE.match(s) or s.upper() == cmd.upper():
            out.append(line)
        elif _SENSITIVE_HEADER.match(s):
            out.append(re.sub(r'"[^"]*"', '"***"', line))
        else:
            out.append("***")
    return "\n".join(out)


class Phone:
    """A phone (or modem) on a serial port."""

    def __init__(self, port, baud=115200, logfile=None, redact=True):
        self.port = port
        self.logfile = logfile
        self.redact = redact
        self.ser = serial.Serial(port, baud, timeout=1)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        self.ser.close()

    def cmd(self, command, timeout=8):
        """Send one AT command and return the phone's raw reply as text."""
        self.ser.reset_input_buffer()
        self.ser.write((command + "\r").encode())
        buf = b""
        end = time.time() + timeout
        while time.time() < end:
            chunk = self.ser.read(self.ser.in_waiting or 1)
            if chunk:
                buf += chunk
                text = buf.decode("latin-1")
                last_line = text.strip().splitlines()[-1] if text.strip() else ""
                if text.endswith("OK\r\n") or "ERROR" in last_line:
                    break
        reply = buf.decode("latin-1", errors="replace")
        self._log(command, reply)
        return reply

    def _log(self, command, reply):
        if not self.logfile:
            return
        shown = redact_reply(command, reply) if self.redact else reply
        try:
            with open(self.logfile, "a", encoding="utf-8") as f:
                f.write(f"[{self.port}] >>> {command}\n{shown}\n\n")
        except OSError:
            pass


def read_phonebook(phone, storage, ucs2=False):
    """Read all contacts from one phonebook storage ("ME" = phone memory, "SM" = SIM).

    Works even on phones that refuse AT+CPBR=? (the "how many entries" query).
    """
    if "ERROR" in phone.cmd(f'AT+CPBS="{storage}"'):
        return []
    used, total = None, 500
    m = re.search(r'\+CPBS:\s*"[^"]*",(\d+),(\d+)', phone.cmd("AT+CPBS?"))
    if m:
        used, total = int(m.group(1)), int(m.group(2))
    m = re.search(r"\+CPBR:\s*\((\d+)[-,](\d+)\)", phone.cmd("AT+CPBR=?"))
    first, last = (int(m.group(1)), int(m.group(2))) if m else (1, total)
    last = min(max(last, first), 2000)

    rows, seen, bad_chunks, step = [], set(), 0, 10
    for start in range(first, last + 1, step):
        end = min(start + step - 1, last)
        reply = phone.cmd(f"AT+CPBR={start},{end}", timeout=10)
        got = parse_cpbr(reply, ucs2)
        if not got and "ERROR" in reply:
            # this phone may only allow one entry at a time
            for i in range(start, end + 1):
                got += parse_cpbr(phone.cmd(f"AT+CPBR={i}"), ucs2)
        for r in got:
            if r["index"] not in seen:
                seen.add(r["index"])
                r["storage"] = storage
                rows.append(r)
        bad_chunks = 0 if got else bad_chunks + 1
        if used and len(rows) >= used:
            break
        if bad_chunks >= (3 if not rows else 5):
            break
    return rows


def read_sms(phone, storage):
    """Read SMS from one storage, trying text mode first and PDU mode as a fallback."""
    phone.cmd("AT+CMGF=1")
    phone.cmd(f'AT+CPMS="{storage}"')
    msgs = parse_cmgl(phone.cmd('AT+CMGL="ALL"', timeout=60))
    if not msgs:
        for status in ("REC READ", "REC UNREAD", "STO SENT", "STO UNSENT"):
            msgs += parse_cmgl(phone.cmd(f'AT+CMGL="{status}"', timeout=30))
    if not msgs:
        phone.cmd("AT+CMGF=0")
        phone.cmd(f'AT+CPMS="{storage}"')
        msgs = parse_cmgl_pdu(phone.cmd("AT+CMGL=4", timeout=60))
        phone.cmd("AT+CMGF=1")
    for m in msgs:
        m["storage"] = storage
    return msgs


def collect(phone, say=print, result=None):
    """Run the whole backup on one phone.

    Returns a dict {"contacts": [...], "messages": [...]}, or None if the phone
    did not answer. Pass `result` to keep partial data if the run is interrupted.
    """
    result = {"contacts": [], "messages": []} if result is None else result
    if "OK" not in phone.cmd("AT", 4):
        return None
    model = phone.cmd("ATI", 4).replace("ATI", "").replace("OK", "").strip()
    say(f"  Phone says: {model or '(no model reported)'}")

    # information only, to help troubleshooting (saved in raw_log.txt)
    say("  Asking the phone what it supports ...")
    for q in ("AT+CLAC", "AT+CPBS=?", "AT+CPMS?", "AT+CSCS=?", "AT+CMGF=?"):
        phone.cmd(q, 10)

    for storage, label in (("ME", "phone memory"), ("SM", "SIM")):
        say(f"  Reading contacts from {label} ...")
        c = read_phonebook(phone, storage)
        if not c:
            phone.cmd('AT+CSCS="UCS2"')
            c = read_phonebook(phone, storage, ucs2=True)
            phone.cmd('AT+CSCS="GSM"')
        result["contacts"] += c
        say(f"  Reading messages from {label} (can take a minute) ...")
        s = read_sms(phone, storage)
        result["messages"] += s
        say(f"  {label}: {len(c)} contacts, {len(s)} messages")
    return result
