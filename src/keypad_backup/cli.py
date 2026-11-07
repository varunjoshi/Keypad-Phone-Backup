"""Command-line interface: `keypad-backup` or `python -m keypad_backup`."""
import argparse
import sys
from pathlib import Path

import serial
from serial.tools import list_ports

from . import __version__
from .exporters import save_all
from .phone import Phone, collect

KEYWORDS = ("samsung", "modem", "mobile", "gsm", "phone")


def rank_ports(ports):
    """Pick serial ports that look like a phone, modem port first. Bluetooth ports are ignored."""
    ranked = []
    for p in ports:
        desc = (p.description or "").lower()
        if "bluetooth" in desc or not any(k in desc for k in KEYWORDS):
            continue
        ranked.append((0 if "modem" in desc else 1, p.device))
    ranked.sort()
    return [device for _, device in ranked]


def choose_ports(port_arg, ports=None, ask=input, say=print):
    if port_arg:
        return [port_arg]
    ports = list(list_ports.comports()) if ports is None else ports
    auto = rank_ports(ports)
    if auto:
        return auto
    if not ports:
        raise SystemExit(
            "No serial ports found. Check the data cable, the USB mode on the phone "
            "(modem / PC Studio, not mass storage) and that the USB driver is installed."
        )
    say("Could not recognise a phone port automatically. Available ports:")
    for i, p in enumerate(ports):
        say(f"  [{i}] {p.device} - {p.description}")
    try:
        return [ports[int(ask("Type the number of the phone port: "))].device]
    except (ValueError, IndexError):
        raise SystemExit("That is not one of the listed numbers.")


def build_parser():
    p = argparse.ArgumentParser(
        prog="keypad-backup",
        description="Back up contacts and SMS from an old keypad phone over USB (AT commands).",
    )
    p.add_argument("-p", "--port", help="serial port, e.g. COM6 or /dev/ttyACM0 (default: find it automatically)")
    p.add_argument("-o", "--out", default="phone_backup", help="output folder (default: phone_backup)")
    p.add_argument("--baud", type=int, default=115200, help="serial speed (default: 115200)")
    p.add_argument("--full-log", action="store_true",
                   help="keep names, numbers and message text in raw_log.txt (hidden by default)")
    p.add_argument("--list-ports", action="store_true", help="list serial ports and exit")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _size(result):
    return len(result["contacts"]) + len(result["messages"])


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.list_ports:
        for p in list_ports.comports():
            print(f"{p.device}\t{p.description}")
        return 0

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    logfile = out / "raw_log.txt"
    logfile.write_text("", encoding="utf-8")

    ports = choose_ports(args.port)
    best = {"contacts": [], "messages": []}
    cur = best
    try:
        for port in ports:
            print(f"\n--- Trying {port} ---")
            cur = {"contacts": [], "messages": []}
            try:
                with Phone(port, args.baud, logfile, redact=not args.full_log) as phone:
                    got = collect(phone, result=cur)
            except (serial.SerialException, OSError) as e:
                print(f"  Could not use {port}: {e}")
                print("  Close Kies / PC Studio or any other program using the phone, then try again.")
                continue
            if got is None:
                print("  No answer on this port.")
                continue
            if _size(cur) > _size(best):
                best = cur
            if _size(cur):
                break
    except KeyboardInterrupt:
        print("\nStopped. Saving what was collected so far ...")
        if _size(cur) > _size(best):
            best = cur

    save_all(out, best["contacts"], best["messages"])
    print(f"\nDone: {len(best['contacts'])} contacts, {len(best['messages'])} messages.")
    print(f"Files are in: {out.resolve()}")
    if not _size(best):
        print("Nothing was read. See 'Troubleshooting' in the README, and open an issue with raw_log.txt "
              "(personal data is hidden in it by default).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
