"""Pure functions that turn raw modem replies into Python data. No hardware needed."""
import re

# GSM 03.38 default alphabet (128 characters) and its escape table
GSM7 = (
    "@£$¥èéùìòÇ\nØø\rÅå"
    "Δ_ΦΓΛΩΠΨΣΘΞ\x1bÆæßÉ"
    " !\"#¤%&'()*+,-./"
    "0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§"
    "¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
GSM7_EXT = {
    0x0A: "\f", 0x14: "^", 0x28: "{", 0x29: "}", 0x2F: "\\",
    0x3C: "[", 0x3D: "~", 0x3E: "]", 0x40: "|", 0x65: "€",
}
DIALABLE = set("+*#0123456789pP,")


def ucs2_to_text(s):
    """Decode a UCS2 hex string (e.g. '004A006F') if it looks like one, else return it unchanged."""
    s = s.strip()
    if s and len(s) % 4 == 0 and re.fullmatch(r"[0-9A-Fa-f]+", s):
        try:
            return bytes.fromhex(s).decode("utf-16-be")
        except Exception:
            pass
    return s


def parse_cpbr(text, ucs2=False):
    """Parse +CPBR: index,"number",type,"name" lines into a list of dicts."""
    rows = []
    for m in re.finditer(r'\+CPBR:\s*(\d+),"([^"]*)",(\d+)(?:,"([^"]*)")?', text):
        number, name = m.group(2), m.group(4) or ""
        if ucs2:
            name = ucs2_to_text(name)
            decoded = ucs2_to_text(number)
            if decoded and set(decoded) <= DIALABLE:
                number = decoded
        rows.append({"index": int(m.group(1)), "name": name, "number": number})
    return rows


def parse_cmgl(text):
    """Parse text-mode AT+CMGL output into a list of message dicts."""
    msgs, cur = [], None
    header = re.compile(r'\+CMGL:\s*(\d+),"([^"]*)","([^"]*)"(?:,[^,]*,"([^"]*)")?')
    for line in text.splitlines():
        m = header.match(line)
        if m:
            if cur:
                msgs.append(cur)
            cur = {
                "index": int(m.group(1)), "status": m.group(2),
                "number": m.group(3), "time": m.group(4) or "", "text": "",
            }
        elif cur is not None and line.strip() and line.strip() != "OK":
            cur["text"] += ("\n" if cur["text"] else "") + line.rstrip()
    if cur:
        msgs.append(cur)
    return msgs


def unpack7(data, count):
    """Unpack `count` GSM 7-bit septets from packed bytes."""
    bits = "".join(f"{b:08b}"[::-1] for b in data)
    out = []
    for i in range(count):
        chunk = bits[i * 7:(i + 1) * 7]
        if len(chunk) < 7:
            break
        out.append(int(chunk[::-1], 2))
    return out


def gsm7_text(septets):
    out, esc = [], False
    for s in septets:
        if esc:
            out.append(GSM7_EXT.get(s, " "))
            esc = False
        elif s == 0x1B:
            esc = True
        else:
            out.append(GSM7[s] if s < 128 else "?")
    return "".join(out)


def decode_addr(data, n, toa):
    if (toa & 0x70) == 0x50:  # alphanumeric sender such as "AX-BANK"
        return gsm7_text(unpack7(data, n * 4 // 7))
    digits = ""
    for byte in data:
        for nib in (byte & 0x0F, byte >> 4):
            if nib < 15:
                digits += "0123456789*#abc"[nib]
    return ("+" if (toa & 0x70) == 0x10 else "") + digits[:n]


def decode_scts(data):
    s = "".join(f"{b & 0xF}{b >> 4}" for b in data)
    return f"{s[0:2]}/{s[2:4]}/{s[4:6]},{s[6:8]}:{s[8:10]}:{s[10:12]}"


def decode_pdu(hexstr):
    """Decode one SMS-DELIVER or SMS-SUBMIT PDU (hex string) into number/time/text."""
    try:
        b = bytes.fromhex(hexstr)
        p = 1 + b[0]  # skip SMSC
        first = b[p]
        p += 1
        mti, udhi = first & 3, bool(first & 0x40)
        if mti not in (0, 1):
            return {"number": "", "time": "", "text": "[unsupported message type]"}
        if mti == 1:
            p += 1  # message reference
        n, toa = b[p], b[p + 1]
        p += 2
        nbytes = (n + 1) // 2
        number = decode_addr(b[p:p + nbytes], n, toa)
        p += nbytes
        p += 1  # PID
        dcs = b[p]
        p += 1
        ts = ""
        if mti == 0:
            ts = decode_scts(b[p:p + 7])
            p += 7
        else:
            vpf = (first >> 3) & 3
            p += {0: 0, 2: 1}.get(vpf, 7)
        udl = b[p]
        p += 1
        ud = b[p:]

        if (dcs & 0xC0) == 0:
            alphabet = ("gsm7", "8bit", "ucs2", "gsm7")[(dcs >> 2) & 3]
        elif (dcs & 0xF0) == 0xE0:
            alphabet = "ucs2"
        elif (dcs & 0xF0) == 0xF0:
            alphabet = "8bit" if dcs & 4 else "gsm7"
        else:
            alphabet = "gsm7"

        udh_len = (ud[0] + 1) if (udhi and ud) else 0
        if alphabet == "gsm7":
            header_septets = (udh_len * 8 + 6) // 7
            text = gsm7_text(unpack7(ud, udl)[header_septets:])
        elif alphabet == "ucs2":
            text = ud[udh_len:udl].decode("utf-16-be", errors="replace")
        else:
            text = ud[udh_len:udl].decode("latin-1", errors="replace")
        return {"number": number, "time": ts, "text": text}
    except Exception as e:  # never crash a whole backup because of one odd message
        return {"number": "", "time": "", "text": f"[could not decode: {e}] {hexstr}"}


def parse_cmgl_pdu(text):
    """Parse AT+CMGL=4 output (PDU mode) into a list of message dicts."""
    msgs = []
    lines = [l.strip() for l in text.splitlines()]
    states = {0: "REC UNREAD", 1: "REC READ", 2: "STO UNSENT", 3: "STO SENT"}
    for i, line in enumerate(lines):
        m = re.match(r"\+CMGL:\s*(\d+),(\d+)", line)
        if m and i + 1 < len(lines) and re.fullmatch(r"[0-9A-Fa-f]+", lines[i + 1]):
            d = decode_pdu(lines[i + 1])
            d["index"] = int(m.group(1))
            d["status"] = states.get(int(m.group(2)), m.group(2))
            msgs.append(d)
    return msgs
