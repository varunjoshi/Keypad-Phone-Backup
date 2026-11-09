# keypad-phone-backup

!\[tests](https://github.com/varunjoshi/keypad-phone-backup/actions/workflows/tests.yml/badge.svg)

Back up the **contacts and SMS** of an old keypad ("feature") phone to your computer over a USB
cable, even when the phone has **no Bluetooth, no SIM and no memory card**.

Many old phones keep everything in internal memory, and the maker's own software (for example
Samsung Kies) is discontinued or hard to find. This tool talks to the phone through its USB modem
interface using standard AT commands, so it needs no vendor software, only the USB driver.

## Tested phones

|Phone|Contacts|SMS|Notes|
|-|-|-|-|
|Samsung SM-B312E|works (phone memory and SIM storage)|no messages returned (unknown whether none were stored or the phone does not expose them)|Windows, Samsung USB driver; port shows up as "SAMSUNG Mobile USB Modem"|

This table has **one phone** in it. Yours may behave differently, so please
[report how it went](../../issues/new?template=phone_report.md) and the table will grow.

## Install

You need Python 3.9 or newer.

```bash
git clone https://github.com/varunjoshi/keypad-phone-backup
cd keypad-phone-backup
pip install .
```

## Use

1. Install your phone's USB driver (on Windows, for Samsung phones: the Samsung USB driver).
2. Connect the phone with a **data** cable. Many cables only charge.
3. If the phone asks for a USB mode, choose **modem / PC Studio / PC Suite**, not "mass storage".
(Mass storage only exposes a memory card, never the internal memory.)
4. Close any phone software running on the computer (it can block the port).
5. Run:

```bash
keypad backup
```
*(You can also use `keypad` or `keypad-backup`)*

It finds the phone port by itself, reads contacts and messages (this can take a few minutes) and
writes a `phone\_backup/` folder:

|File|What it is|
|-|-|
|`contacts.csv`|Contacts for Excel / Google Sheets. `storage` says whether a contact came from the phone (`ME`) or the SIM (`SM`)|
|`contacts.vcf`|The same contacts as a vCard file, ready to import into Google Contacts, iPhone or another phone|
|`messages.csv`|SMS (empty if the phone did not return any)|
|`raw\_log.txt`|What the phone answered, for troubleshooting. Personal data is hidden (see Privacy)|

### Options

|Option|Meaning|
|-|-|
|`-p`, `--port COM6`|Use this port instead of detecting it (`/dev/ttyACM0` on Linux)|
|`-o`, `--out DIR`|Output folder (default `phone\_backup`)|
|`--baud N`|Serial speed (default 115200)|
|`--list-ports`|Show serial ports and exit (or run `keypad list-ports`)|
|`--full-log`|Keep names, numbers and message text in `raw\_log.txt`. **Never share that file.**|

If the same person appears twice (phone and SIM), Google Contacts has a "Merge \& fix" tool.

## Troubleshooting

* **"No serial ports found"**: check the cable, the USB mode on the phone, and the driver. On
Windows, open Device Manager and look under "Ports (COM \& LPT)" or "Modems".
* **A "Removable Disk" popup appears**: the phone is in mass-storage mode. Click Cancel and
switch the phone to modem / PC Studio mode.
* **"No answer on this port"**: wait a few seconds after plugging the phone in, unplug and replug
it, and run again. During testing the first attempt failed and the next one worked.
* **"Could not use COMx"**: another program is holding the port. Close it and retry.
* **0 contacts and 0 messages**: the phone may not expose its data this way. Open an issue with
your `raw\_log.txt` (check it first) and your phone model.
* **Garbled names**: tell us the model; some phones use a different character encoding.
* **Linux / macOS**: should work with `pip install .` and the port `/dev/ttyACM0` (Linux) or
`/dev/tty.usbmodem\*` (macOS), but this is **untested**. On Linux you may need
`sudo usermod -aG dialout $USER` and a new login.

## Privacy

* Everything stays on your computer. The tool makes no network connections.
* `raw\_log.txt` hides contact names, numbers and message text by default. Look at it before you
post it anywhere. `--full-log` turns the hiding off.
* `contacts.\*` and `messages.csv` are plain, unencrypted text files. Keep them somewhere safe.
* The included `.gitignore` keeps backup files out of git. If you fork this project, keep it.

## What it sends to your phone

Only standard AT commands: `AT`, `ATI`, `AT+CLAC`, `AT+CPBS`, `AT+CPBR`, `AT+CPMS`,
`AT+CMGF`, `AT+CMGL` and `AT+CSCS`.

It never writes or deletes contacts or messages. It does switch a few temporary settings (which
phonebook / message storage is selected, text or PDU mode, character set), and, as the AT
standard describes, listing messages can mark unread ones as read.

## Limitations

* Contacts and SMS only. No photos, music, files, calendar or call log.
* Long SMS arrive as separate parts and are not merged yet.
* The phone must expose a modem / serial interface over USB. Some do not.
* Tested on one phone so far.

## Contributing

Phone reports are the most useful contribution, see [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
pip install -e ".\[test]"
pytest
```

## License

MIT, see [LICENSE](LICENSE). This project is not affiliated with Samsung or any phone maker.

