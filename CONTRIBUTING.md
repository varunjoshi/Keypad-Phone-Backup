# Contributing

The most useful contribution is a **phone report**: run the tool on your phone and open an issue
using the "Phone report" template. Every model behaves a little differently, and reports are how
the compatibility table in the README grows.

## Privacy first

`raw\_log.txt` hides contact names, numbers and message text by default. Still, **look at the file
before you post it**, and never post output from `--full-log` or your `phone\_backup/` folder.

## Development

```bash
git clone https://github.com/varunjoshi/keypad-phone-backup
cd keypad-phone-backup
pip install -e ".\[test]"
pytest
```

The tests use a fake phone (`tests/fakes.py`), so no hardware is needed. If you add support for a
new quirk, add a test that reproduces the phone's reply (with fake data).

## Ideas that would help

* Merging multi-part (long) SMS into one message
* Reading calendar, notes and call logs where phones support it
* Export to other formats
* Linux and macOS testing

