#!/usr/bin/env python3
"""Probe the AutoLink dongle for Android Open Accessory (AOA) support.

The dongle enumerates as 2717:ff40 (Xiaomi MTP) and resets roughly every
22 seconds.  A head unit is expected to send AOA control requests during
that window.  This script retries until it catches the device.

Usage:
    sudo python3 aoa_probe.py probe   # GET_PROTOCOL only
    sudo python3 aoa_probe.py start   # strings + ACCESSORY_START
"""

import subprocess
import sys
import time

import usb.core
import usb.util

VID = 0x2717
PID = 0xFF40

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
        print("lsusb after START:", flush=True)
        subprocess.run(["lsusb"], check=False)
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
    mode = sys.argv[1] if len(sys.argv) > 1 else "probe"
    deadline = time.time() + 90
    while time.time() < deadline:
        if probe_once(mode):
            return 0
        time.sleep(0.25)
    print("timed out waiting for dongle", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
