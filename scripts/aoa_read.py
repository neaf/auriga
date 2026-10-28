#!/usr/bin/env python3
"""Listen on the AOA bulk-IN endpoint and print anything the dongle sends."""

import sys
import time

import usb.core
import usb.util

VID = 0x18D1
PID = 0x2D00


def main():
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        print("dongle not found", flush=True)
        return 1

    try:
        dev.set_configuration()
    except usb.core.USBError as exc:
        print(f"set_configuration: {exc}", flush=True)

    usb.util.claim_interface(dev, 0)
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
    print(f"IN={ep_in.bEndpointAddress:#x} OUT={ep_out.bEndpointAddress:#x}", flush=True)

    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            data = dev.read(ep_in.bEndpointAddress, 512, timeout=500)
            print(f"RX {len(data)}: {bytes(data).hex()}", flush=True)
        except usb.core.USBError as exc:
            if exc.errno == 110:  # ETIMEDOUT
                continue
            print(f"read error: {exc}", flush=True)
            time.sleep(0.5)

    usb.util.release_interface(dev, 0)
    usb.util.dispose_resources(dev)
    return 0


if __name__ == "__main__":
    sys.exit(main())
