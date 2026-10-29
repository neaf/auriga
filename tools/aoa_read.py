#!/usr/bin/env python3
"""Listen on the AOA bulk-IN endpoint and print anything the dongle sends.

Stop `autoapp` (or the whole Auriga pair) first: the head unit claims the
dongle's interface, and pyusb cannot claim it twice. Run it with the venv that
has pyusb:

    .venv/bin/python tools/aoa_read.py
"""

import sys
import time

import usb.core
import usb.util

VID = 0x18D1
PID = 0x2D00

# A bulk read that times out raises USBError; the errno is platform-specific
# (Darwin 60 = ETIMEDOUT, Linux 110). Both mean "nothing arrived", not failure.
TIMEOUT_ERRNOS = (60, 110)


def main():
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        print("dongle not found (AOA 18d1:2d00); is it switched and connected?", flush=True)
        return 1

    try:
        dev.set_configuration()
    except usb.core.USBError as exc:
        print(f"set_configuration: {exc}", flush=True)

    try:
        usb.util.claim_interface(dev, 0)
    except usb.core.USBError as exc:
        print(
            f"cannot claim interface 0: {exc}\n"
            "another process owns the dongle (stop autoapp / scripts/auriga.sh stop), "
            "or the tool needs to run as the same user",
            flush=True,
        )
        usb.util.dispose_resources(dev)
        return 1

    try:
        cfg = dev.get_active_configuration()
        intf = cfg[(0, 0)]
        ep_in = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
            == usb.util.ENDPOINT_IN,
        )
        ep_out = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
            == usb.util.ENDPOINT_OUT,
        )
        if ep_in is None:
            print("no bulk-IN endpoint on interface 0", flush=True)
            return 1
        print(
            f"IN={ep_in.bEndpointAddress:#x} "
            f"OUT={ep_out.bEndpointAddress:#x if ep_out else 'none'}",
            flush=True,
        )

        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                data = dev.read(ep_in.bEndpointAddress, 512, timeout=500)
                print(f"RX {len(data)}: {bytes(data).hex()}", flush=True)
            except usb.core.USBError as exc:
                if exc.errno in TIMEOUT_ERRNOS:
                    continue
                print(f"read error: {exc}", flush=True)
                time.sleep(0.5)
    finally:
        try:
            usb.util.release_interface(dev, 0)
        except usb.core.USBError:
            pass
        usb.util.dispose_resources(dev)
    return 0


if __name__ == "__main__":
    sys.exit(main())
