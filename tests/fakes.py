"""A fake phone that answers AT commands, so tests need no hardware."""
import re


class FakePhone:
    """Mimics a feature phone that refuses AT+CPBR=? (like the Samsung SM-B312E)."""

    def __init__(self, contacts=None, range_ok=True, text_sms="", pdu_sms="", answers=True):
        self.contacts = contacts or {}          # {index: (number, name)} stored in "ME"
        self.range_ok = range_ok                # False = phone only allows one entry per command
        self.text_sms = text_sms                # reply to AT+CMGL="ALL" for storage "ME"
        self.pdu_sms = pdu_sms                  # reply to AT+CMGL=4 for storage "ME"
        self.answers = answers
        self.pb_storage = "ME"
        self.sms_storage = "ME"
        self.calls = []

    def cmd(self, command, timeout=0):
        self.calls.append(command)
        if not self.answers:
            return ""
        if command == "AT":
            return "AT\r\n\r\nOK\r\n"
        if command == "ATI":
            return "ATI\r\nSamsung TEST-1\r\n\r\nOK\r\n"
        m = re.match(r'AT\+CPBS="(\w+)"$', command)
        if m:
            self.pb_storage = m.group(1)
            return "OK\r\n"
        book = self.contacts if self.pb_storage == "ME" else {}
        if command == "AT+CPBS?":
            return f'+CPBS: "{self.pb_storage}",{len(book)},500\r\nOK\r\n'
        if command == "AT+CPBR=?":
            return "ERROR\r\n"
        m = re.match(r"AT\+CPBR=(\d+)(?:,(\d+))?$", command)
        if m:
            a = int(m.group(1))
            b = int(m.group(2)) if m.group(2) else None
            if b is not None and not self.range_ok:
                return "ERROR\r\n"
            out = "".join(
                f'+CPBR: {i},"{book[i][0]}",145,"{book[i][1]}"\r\n'
                for i in range(a, (b or a) + 1) if i in book
            )
            if out:
                return out + "OK\r\n"
            return "ERROR\r\n" if b is None else "OK\r\n"
        m = re.match(r'AT\+CPMS="(\w+)"$', command)
        if m:
            self.sms_storage = m.group(1)
            return "OK\r\n"
        if command == 'AT+CMGL="ALL"':
            return (self.text_sms + "OK\r\n") if self.sms_storage == "ME" and self.text_sms else "OK\r\n"
        if command == "AT+CMGL=4":
            return (self.pdu_sms + "OK\r\n") if self.sms_storage == "ME" and self.pdu_sms else "OK\r\n"
        return "OK\r\n"
