from keypad_backup.phone import collect, read_phonebook, read_sms, redact_reply

from .fakes import FakePhone
from .test_parsers import deliver_7bit

BOOK = {1: ("+919812345678", "Mom"), 2: ("9876543210", "Rahul"), 3: ("12345", "Office")}


def test_phonebook_with_range_reads():
    phone = FakePhone(contacts=BOOK, range_ok=True)
    rows = read_phonebook(phone, "ME")
    assert [r["name"] for r in rows] == ["Mom", "Rahul", "Office"]
    assert all(r["storage"] == "ME" for r in rows)


def test_phonebook_when_phone_only_allows_single_reads():
    phone = FakePhone(contacts=BOOK, range_ok=False)
    assert len(read_phonebook(phone, "ME")) == 3


def test_phonebook_works_when_range_query_errors():
    # the fake always answers AT+CPBR=? with ERROR, exactly like the real SM-B312E did
    phone = FakePhone(contacts=BOOK)
    rows = read_phonebook(phone, "ME")
    assert "AT+CPBR=?" in phone.calls  # it did ask, got ERROR ...
    assert len(rows) == 3              # ... and read the contacts anyway


def test_empty_storage_stops_quickly():
    phone = FakePhone(contacts={})
    assert read_phonebook(phone, "SM") == []
    assert len(phone.calls) < 15


def test_sms_text_mode():
    text = '+CMGL: 1,"REC READ","+911234567890",,"26/11/07,10:00:00+22"\r\nHello\r\n'
    msgs = read_sms(FakePhone(text_sms=text), "ME")
    assert msgs[0]["text"] == "Hello" and msgs[0]["storage"] == "ME"


def test_sms_falls_back_to_pdu_mode():
    pdu = deliver_7bit("+919812345678", "From PDU")
    reply = f"+CMGL: 1,1,,30\r\n{pdu}\r\n"
    msgs = read_sms(FakePhone(pdu_sms=reply), "ME")
    assert msgs[0]["text"] == "From PDU"


def test_collect_full_run():
    pdu = deliver_7bit("+919812345678", "Saved message")
    phone = FakePhone(contacts=BOOK, pdu_sms=f"+CMGL: 1,1,,30\r\n{pdu}\r\n")
    said = []
    result = collect(phone, say=said.append)
    assert len(result["contacts"]) == 3
    assert result["messages"][0]["text"] == "Saved message"
    assert any("Samsung TEST-1" in s for s in said)


def test_collect_returns_none_when_phone_is_silent():
    assert collect(FakePhone(answers=False), say=lambda s: None) is None


def test_collect_keeps_partial_results_in_given_dict():
    phone = FakePhone(contacts=BOOK)
    keep = {"contacts": [], "messages": []}
    collect(phone, say=lambda s: None, result=keep)
    assert len(keep["contacts"]) == 3


# --- log redaction: names, numbers and message text must not appear ---
def test_redact_contacts():
    reply = 'AT+CPBR=1,10\r\n+CPBR: 1,"+919812345678",145,"Mom"\r\nOK\r\n'
    shown = redact_reply("AT+CPBR=1,10", reply)
    assert "Mom" not in shown and "9812345678" not in shown
    assert "+CPBR: 1," in shown and "OK" in shown


def test_redact_sms_body_even_if_it_starts_with_at_or_contains_error():
    reply = ('AT+CMGL="ALL"\r\n+CMGL: 1,"REC READ","+911234567890",,"26/11/07,10:00:00+22"\r\n'
             "At 5 pm meet me, secret\r\nError code is my PIN 4321\r\nOK\r\n")
    shown = redact_reply('AT+CMGL="ALL"', reply)
    for secret in ("secret", "4321", "At 5 pm", "1234567890"):
        assert secret not in shown
    assert shown.rstrip().endswith("OK")


def test_redact_pdu_lines():
    pdu = deliver_7bit("+919812345678", "private text")
    shown = redact_reply("AT+CMGL=4", f"+CMGL: 1,1,,30\r\n{pdu}\r\nOK\r\n")
    assert pdu not in shown


def test_redact_leaves_harmless_commands_alone():
    reply = 'AT+CPBS?\r\n+CPBS: "ME",544,1000\r\nOK\r\n'
    assert redact_reply("AT+CPBS?", reply) == reply
    reply = "+CPBR: (1-1000),40,14\r\nOK\r\n"
    assert redact_reply("AT+CPBR=?", reply) == reply
