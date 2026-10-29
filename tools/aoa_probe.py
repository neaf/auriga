#!/usr/bin/env python3
"""Probe the AutoLink dongle for Android Open Accessory (AOA) support.

The dongle enumerates as 2717:ff40 (Xiaomi MTP) and resets roughly every
22 seconds (`unverified`).  A head unit is expected to send AOA control requests
during that window.  This script retries until it catches the device.

Run it with the venv that has pyusb, and not while `autoapp` owns the dongle:

    sudo .venv/bin/python tools/aoa_probe.py probe   # GET_PROTOCOL only
    sudo .venv/bin/python tools/aoa_probe.py start   # strings + ACCESSORY_START
"""

import subprocess
import sys
import time

import usb.core
import usb.util

VID = 0x2717
PID = 0xFF40

USAGE = "usage: aoa_probe.py [probe|start]"

# AOA control requests (device level)
ACCESSORY_GET_PROTOCOL = 51
ACCESSORY_SEND_STRING = 52
ACCESSORY_START = 53

# String indices used by AOA
STRINGS = [
    "Auriga",                       # 0 manufacturer
    "Auriga Pi Headunit",           # 1 model
    "Auriga AA capture",            # 2 description
    "1.0",                          # 3 version
    "https://auriga.invalid",       # 4 URI
    "auriga-pi",                    # 5 serial
]


def find_device():
    return usb.core.find(idVendor=VID, idProduct=PID)


def print_usb_devices():
    """List USB devices with the host's own tool; macOS has no `lsusb`."""
    if sys.platform == "darwin":
        command = ["ioreg", "-p", "IOUSB", "-l", "-w", "0"]
        keywords = ("AutoLink", "idProduct", "idVendor", "USB Product Name")
    else:
        command = ["lsusb"]
        keywords = None

    try:
        result = subprocess.run(
            command, check=False, capture_output=True, text=True, timeout=10
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
        print(f"cannot list USB devices ({command[0]}: {exc})", flush=True)
        return

    lines = result.stdout.splitlines()
    if keywords is not None:
        lines = [
            line.strip() for line in lines
            if any(keyword in line for keyword in keywords)
        ]
    for line in lines:
        print(line, flush=True)


def probe_once(mode):
    dev = find_device()
    if dev is None:
        return False

    try:
        print(f"found bus={dev.bus} addr={dev.address}", flush=True)
        raw = dev.ctrl_transfer(0xC0, ACCESSORY_GET_PROTOCOL, 0, 0, 2, timeout=1000)
        version = raw[0] | (raw[1] << 8) if len(raw) >= 2 else None
        print(f"AOA GET_PROTOCOL -> {list(raw)} version={version}", flush=True)

        if mode != "start":
            return True

        for index, value in enumerate(STRINGS):
            sent = dev.ctrl_transfer(
                0x40, ACCESSORY_SEND_STRING, 0, index,
                (value + "\0").encode(), timeout=1000,
            )
            print(f"SEND_STRING[{index}] {value!r} -> {sent}", flush=True)

        print("sending ACCESSORY_START", flush=True)
        try:
            dev.ctrl_transfer(0x40, ACCESSORY_START, 0, 0, 0, timeout=1000)
        except usb.core.USBError as exc:
            print(f"START raised {exc} (expected if it re-enumerates)", flush=True)

        time.sleep(3)
        print("USB devices after START:", flush=True)
        print_usb_devices()
        return True
    except usb.core.USBError as exc:
        print(f"USB error: {exc}", flush=True)
        return False
    finally:
        try:
            usb.util.dispose_resources(dev)
        except usb.core.USBError:
            pass


def main():
    if len(sys.argv) > 2:
        print(USAGE, file=sys.stderr)
        return 2
    mode = sys.argv[1] if len(sys.argv) > 1 else "probe"
    if mode not in ("probe", "start"):
        print(USAGE, file=sys.stderr)
        return 2
    deadline = time.time() + 90
    while time.time() < deadline:
        if probe_once(mode):
            return 0
        time.sleep(0.25)
    print("timed out waiting for dongle", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
