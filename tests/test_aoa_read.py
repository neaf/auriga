"""`tools/aoa_read.py` runs without a dongle.

The tool is the only code that reads the AOA bulk-IN endpoint and nothing imports
it, so `py_compile` never sees a runtime error there: a conditional inside an
f-string format spec made the endpoint banner raise on every run. These tests
import the module against a stub `usb` (pyusb is a `.venv`-only extra) and drive
`main()` with a fake device.
"""

import io
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock


class USBError(Exception):
    def __init__(self, message, errno=None):
        super().__init__(message)
        self.errno = errno


class Endpoint:
    def __init__(self, address):
        self.bEndpointAddress = address


class Interface:
    def __init__(self, endpoints):
        self.endpoints = endpoints

    def __iter__(self):
        return iter(self.endpoints)


class Config:
    def __init__(self, interface):
        self.interface = interface

    def __getitem__(self, key):
        assert key == (0, 0), key
        return self.interface


class Device:
    def __init__(self, endpoints, read_error=None):
        self.interface = Interface([Endpoint(address) for address in endpoints])
        self.read_error = read_error
        self.reads = []

    def set_configuration(self):
        pass

    def get_active_configuration(self):
        return Config(self.interface)

    def read(self, address, size, timeout=None):
        self.reads.append((address, size, timeout))
        if self.read_error is not None:
            raise self.read_error
        return [0x01]


def fake_usb(device):
    """Minimal `usb.core` + `usb.util` surface used by `aoa_read.main`."""
    core = mock.Mock()
    core.find.return_value = device
    core.USBError = USBError

    util = mock.Mock()
    util.ENDPOINT_IN = 0x80
    util.ENDPOINT_OUT = 0x00
    util.endpoint_direction = lambda address: address & 0x80

    def find_descriptor(descriptor, custom_match=None):
        for endpoint in descriptor:
            if custom_match is None or custom_match(endpoint):
                return endpoint
        return None

    util.find_descriptor = find_descriptor

    usb = mock.Mock()
    usb.core = core
    usb.util = util
    return usb


def load_tool(usb):
    """Import `tools.aoa_read` with `usb` stubbed; return the module."""
    sys.modules.pop("tools.aoa_read", None)
    with mock.patch.dict(sys.modules, {"usb": usb, "usb.core": usb.core, "usb.util": usb.util}):
        import tools.aoa_read as module

    return module


class DescribeEndpointsTest(unittest.TestCase):
    def test_both_endpoints(self):
        module = load_tool(fake_usb(Device([0x81, 0x02])))
        self.assertEqual(module.describe_endpoints(Endpoint(0x81), Endpoint(0x02)),
                         "IN=0x81 OUT=0x2")

    def test_without_an_out_endpoint(self):
        module = load_tool(fake_usb(Device([0x81])))
        self.assertEqual(module.describe_endpoints(Endpoint(0x81), None), "IN=0x81 OUT=none")


class MainTest(unittest.TestCase):
    def run_main(self, device):
        module = load_tool(fake_usb(device))
        output = io.StringIO()
        # `time()` calls: the deadline, then one loop condition that is inside the
        # window, then one that has passed it, so exactly one read happens.
        with mock.patch.object(module.time, "time", side_effect=[0, 0, 10 ** 6]):
            with redirect_stdout(output):
                status = module.main()
        return status, output.getvalue()

    def test_prints_the_banner_and_reads(self):
        device = Device([0x81, 0x02])
        status, output = self.run_main(device)
        self.assertEqual(status, 0)
        self.assertIn("IN=0x81 OUT=0x2", output)
        self.assertEqual(device.reads, [(0x81, 512, 500)])

    def test_prints_the_banner_without_an_out_endpoint(self):
        status, output = self.run_main(Device([0x81]))
        self.assertEqual(status, 0)
        self.assertIn("IN=0x81 OUT=none", output)

    def test_a_timeout_is_not_an_error(self):
        device = Device([0x81, 0x02], read_error=USBError("timeout", errno=60))
        status, output = self.run_main(device)
        self.assertEqual(status, 0)
        self.assertNotIn("read error", output)

    def test_a_missing_dongle_exits_1(self):
        module = load_tool(fake_usb(None))
        output = io.StringIO()
        with redirect_stdout(output):
            status = module.main()
        self.assertEqual(status, 1)
        self.assertIn("dongle not found", output.getvalue())


if __name__ == "__main__":
    unittest.main()
