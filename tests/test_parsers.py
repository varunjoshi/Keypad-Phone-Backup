from keypad_backup import parsers as p


# --- helpers that build SMS PDUs, so decoding can be checked end to end ---
def pack7(text):
    sept = [p.GSM7.index(ch) for ch in text]
    bits = "".join(f"{s:07b}"[::-1] for s in sept)
    bits += "0" * (-len(bits) % 8)
    return bytes(int(bits[i:i + 8][::-1], 2) for i in range(0, len(bits), 8)), len(sept)


def bcd(number):
    d = number.lstrip("+")
    if len(d) % 2:
        d += "F"
    return bytes(int(d[i + 1] + d[i], 16) for i in range(0, len(d), 2))


SCTS = bytes([0x62, 0x11, 0x70, 0x01, 0x90, 0x00, 0x22])


def deliver_7bit(number, text):
    ud, n = pack7(text)
    return (b"\x00\x04" + bytes([len(number.lstrip("+")), 0x91]) + bcd(number)
            + b"\x00\x00" + SCTS + bytes([n]) + ud).hex().upper()


def test_gsm7_table_has_128_characters():
    assert len(p.GSM7) == 128


def test_known_gsm7_sample():
    # "hellohello" is the classic textbook example of a packed 7-bit message
    assert p.gsm7_text(p.unpack7(bytes.fromhex("E8329BFD4697D9EC37"), 10)) == "hellohello"


def test_parse_cpbr():
    reply = ('AT+CPBR=1,10\r\n+CPBR: 1,"+919812345678",145,"Mom"\r\n'
             '+CPBR: 2,"9876543210",129,"Rahul Office"\r\n\r\nOK\r\n')
    assert p.parse_cpbr(reply) == [
        {"index": 1, "name": "Mom", "number": "+919812345678"},
        {"index": 2, "name": "Rahul Office", "number": "9876543210"},
    ]


def test_parse_cpbr_ucs2_names():
    reply = '+CPBR: 1,"12345",129,"004D006F006D"\r\nOK\r\n'
    assert p.parse_cpbr(reply, ucs2=True)[0]["name"] == "Mom"


def test_parse_cpbr_ucs2_keeps_plain_numbers():
    reply = '+CPBR: 1,"98765432",129,"0041"\r\nOK\r\n'  # 8 digits, looks like hex but is a real number
    assert p.parse_cpbr(reply, ucs2=True)[0]["number"] == "98765432"


def test_parse_cmgl_text_mode():
    reply = ('AT+CMGL="ALL"\r\n'
             '+CMGL: 1,"REC READ","+919812345678",,"26/11/07,10:00:00+22"\r\nHello, how are you?\r\n'
             '+CMGL: 2,"STO SENT","+919812345678",,\r\nI am fine\r\nsecond line\r\n'
             'OK\r\n')
    msgs = p.parse_cmgl(reply)
    assert [m["index"] for m in msgs] == [1, 2]
    assert msgs[0]["time"] == "26/11/07,10:00:00+22"
    assert msgs[1]["text"] == "I am fine\nsecond line"
    assert msgs[1]["time"] == ""


def test_decode_pdu_7bit():
    d = p.decode_pdu(deliver_7bit("+919812345678", "Hello, OTP is 1234"))
    assert d == {"number": "+919812345678", "time": "26/11/07,10:09:00", "text": "Hello, OTP is 1234"}


def test_decode_pdu_ucs2():
    text = "नमस्ते"
    ud = text.encode("utf-16-be")
    pdu = (b"\x00\x04" + bytes([12, 0x91]) + bcd("+919812345678") + b"\x00\x08" + SCTS
           + bytes([len(ud)]) + ud).hex()
    assert p.decode_pdu(pdu)["text"] == text


def test_decode_pdu_alphanumeric_sender():
    sender = "AX-BANK"
    addr, _ = pack7(sender)
    n = (len(sender) * 7 + 3) // 4  # number of useful semi-octets
    ud, count = pack7("OTP is 123456")
    pdu = (b"\x00\x04" + bytes([n, 0xD0]) + addr + b"\x00\x00" + SCTS + bytes([count]) + ud).hex()
    d = p.decode_pdu(pdu)
    assert d["number"] == sender
    assert d["text"] == "OTP is 123456"


def test_decode_pdu_garbage_does_not_crash():
    assert "could not decode" in p.decode_pdu("ZZ")["text"]      # not valid hex
    assert "could not decode" in p.decode_pdu("0004")["text"]    # truncated PDU


def test_parse_cmgl_pdu():
    pdu = deliver_7bit("+919812345678", "Hi there")
    reply = f"AT+CMGL=4\r\n+CMGL: 3,1,,40\r\n{pdu}\r\n+CMGL: 4,3,,30\r\n{pdu}\r\n\r\nOK\r\n"
    msgs = p.parse_cmgl_pdu(reply)
    assert [(m["index"], m["status"]) for m in msgs] == [(3, "REC READ"), (4, "STO SENT")]
    assert msgs[0]["text"] == "Hi there"
