"""Save results as CSV and vCard files."""
import csv
from pathlib import Path


def _vcard_escape(s):
    return s.replace("\\", "\\\\").replace("\r", "").replace("\n", "\\n").replace(";", "\\;").replace(",", "\\,")


def save_contacts_csv(path, contacts):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig so Excel shows all scripts correctly
        w = csv.DictWriter(f, fieldnames=["storage", "index", "name", "number"], extrasaction="ignore")
        w.writeheader()
        w.writerows(contacts)


def save_contacts_vcf(path, contacts):
    with open(path, "w", newline="", encoding="utf-8") as f:
        for c in contacts:
            name = _vcard_escape(c.get("name", ""))
            lines = ["BEGIN:VCARD", "VERSION:3.0", f"N:;{name};;;", f"FN:{name}"]
            if c.get("number"):
                lines.append(f"TEL:{_vcard_escape(c['number'])}")
            lines.append("END:VCARD")
            f.write("\r\n".join(lines) + "\r\n")


def save_messages_csv(path, messages):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(
            f, fieldnames=["storage", "index", "status", "number", "time", "text"], extrasaction="ignore"
        )
        w.writeheader()
        w.writerows(messages)


def save_all(out_dir, contacts, messages):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    save_contacts_csv(out / "contacts.csv", contacts)
    save_contacts_vcf(out / "contacts.vcf", contacts)
    save_messages_csv(out / "messages.csv", messages)
