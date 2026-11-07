import csv

from keypad_backup.exporters import save_all

CONTACTS = [
    {"storage": "ME", "index": 1, "name": "Mom", "number": "+919812345678"},
    {"storage": "ME", "index": 2, "name": "Smith, John; Jr.", "number": "12345"},
    {"storage": "SM", "index": 1, "name": "नमस्ते", "number": ""},
]
MESSAGES = [{"storage": "ME", "index": 1, "status": "REC READ", "number": "+91", "time": "t", "text": "a\nb"}]


def test_save_all_creates_files(tmp_path):
    save_all(tmp_path, CONTACTS, MESSAGES)
    assert {f.name for f in tmp_path.iterdir()} == {"contacts.csv", "contacts.vcf", "messages.csv"}


def test_csv_roundtrip(tmp_path):
    save_all(tmp_path, CONTACTS, MESSAGES)
    with open(tmp_path / "contacts.csv", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert [r["name"] for r in rows] == ["Mom", "Smith, John; Jr.", "नमस्ते"]
    with open(tmp_path / "messages.csv", newline="", encoding="utf-8-sig") as f:
        assert list(csv.DictReader(f))[0]["text"] == "a\nb"


def test_vcf_is_valid_and_escaped(tmp_path):
    save_all(tmp_path, CONTACTS, MESSAGES)
    vcf = (tmp_path / "contacts.vcf").read_bytes().decode("utf-8")
    assert vcf.count("BEGIN:VCARD") == 3 and vcf.count("END:VCARD") == 3
    assert "N:;Mom;;;\r\nFN:Mom\r\nTEL:+919812345678\r\n" in vcf
    assert "FN:Smith\\, John\\; Jr." in vcf
    assert "TEL:" not in vcf.split("BEGIN:VCARD")[3]  # no empty TEL line for a contact without a number
