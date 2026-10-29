import os
import struct
import tempfile
import unittest
from pathlib import Path

from stream.lib.h264 import (
    FrameAssembler,
    GopBuffer,
    avcc_sample,
    build_avcc,
    extract_sps_pps,
    find_last_idr,
    split_nals,
    sps_pps_from_bytes,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SAMPLE = FIXTURES / "sample.h264"
START = b"\x00\x00\x00\x01"

SPS = bytes([0x67, 0x42, 0x80, 0x1F, 0xDA, 0x01, 0x40, 0x16, 0xE8, 0x06, 0x05, 0xA8])
SPS2 = bytes([0x67, 0x42, 0x80, 0x1F, 0xDA, 0x01, 0x40, 0x16, 0xE8, 0x06, 0x05, 0xA9])
PPS = bytes([0x68, 0xCE, 0x06, 0xE2])
IDR = bytes([0x65, 0x88, 0x84, 0x00, 0x21])
DELTA = bytes([0x41, 0x9A, 0x22])


class TempFileMixin:
    def write_temp(self, data: bytes) -> str:
        handle = tempfile.NamedTemporaryFile(delete=False)
        handle.write(data)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return handle.name


class SplitNalsTest(unittest.TestCase):
    def test_holds_back_the_last_nal(self):
        nals, rest = split_nals(START + SPS + START + PPS + START + IDR)
        self.assertEqual(nals, [SPS, PPS])
        self.assertEqual(rest, START + IDR)

    def test_resumes_from_the_remainder(self):
        _, rest = split_nals(START + SPS + START + PPS)
        nals, rest = split_nals(rest + START + IDR + START + DELTA)
        self.assertEqual(nals, [PPS, IDR])
        self.assertEqual(rest, START + DELTA)

    def test_three_byte_start_codes(self):
        nals, rest = split_nals(b"\x00\x00\x01" + SPS + b"\x00\x00\x01" + PPS)
        self.assertEqual(nals, [SPS])
        self.assertEqual(rest, b"\x00\x00\x01" + PPS)

    def test_emulation_prevention_is_not_a_start_code(self):
        nal = bytes([0x65, 0x00, 0x00, 0x03, 0x01])
        nals, rest = split_nals(START + nal + START + DELTA)
        self.assertEqual(nals, [nal])
        self.assertEqual(rest, START + DELTA)

    def test_no_start_code_keeps_the_tail(self):
        self.assertEqual(split_nals(b"\x01\x02\x03"), ([], b"\x01\x02\x03"))
        self.assertEqual(split_nals(b"\x01\x02\x03\x04\x05"), ([], b"\x02\x03\x04\x05"))

    def test_empty_input(self):
        self.assertEqual(split_nals(b""), ([], b""))


class SpsPpsTest(TempFileMixin, unittest.TestCase):
    def test_extracts_from_the_fixture(self):
        self.assertEqual(extract_sps_pps(str(SAMPLE)), (SPS, PPS))

    def test_bytes_without_codec_config(self):
        self.assertEqual(sps_pps_from_bytes(START + IDR), (None, None))

    def test_missing_file(self):
        self.assertEqual(extract_sps_pps("/nonexistent/sample.h264"), (None, None))

    def test_first_sps_wins(self):
        data = START + SPS2 + START + SPS + START + PPS + START + IDR
        sps, pps = sps_pps_from_bytes(data)
        self.assertEqual((sps, pps), (SPS2, PPS))

    def test_a_truncated_sps_is_not_a_parameter_set(self):
        # A partially flushed segment head gives a 1-3 byte "SPS".
        short = bytes([0x67, 0x42])
        self.assertEqual(
            sps_pps_from_bytes(START + short + START + PPS + START + IDR),
            (None, PPS),
        )

    def test_limit_stops_the_read(self):
        path = self.write_temp(START + IDR + START + SPS + START + PPS)
        self.assertEqual(extract_sps_pps(path, limit=len(START + IDR)), (None, None))


class BuildAvccTest(unittest.TestCase):
    def test_layout(self):
        avcc = build_avcc(SPS, PPS)
        self.assertEqual(avcc[:6], bytes([1, SPS[1], SPS[2], SPS[3], 0xFF, 0xE1]))
        self.assertEqual(avcc[6:8], struct.pack(">H", len(SPS)))
        self.assertEqual(avcc[8:8 + len(SPS)], SPS)
        self.assertEqual(avcc[8 + len(SPS)], 1)
        self.assertEqual(
            avcc[9 + len(SPS):11 + len(SPS)], struct.pack(">H", len(PPS))
        )
        self.assertEqual(avcc[11 + len(SPS):], PPS)
        self.assertEqual(len(avcc), 11 + len(SPS) + len(PPS))

    def test_a_truncated_sps_is_rejected(self):
        with self.assertRaises(ValueError):
            build_avcc(bytes([0x67, 0x42]), PPS)
        with self.assertRaises(ValueError):
            build_avcc(SPS, b"")


class AvccSampleTest(unittest.TestCase):
    def test_length_prefixes(self):
        self.assertEqual(avcc_sample([SPS, PPS]), struct.pack(">I", len(SPS)) + SPS + struct.pack(">I", len(PPS)) + PPS)

    def test_empty_nals_are_skipped(self):
        self.assertEqual(avcc_sample([b"", IDR]), struct.pack(">I", len(IDR)) + IDR)

    def test_nothing(self):
        self.assertEqual(avcc_sample([]), b"")


class FrameAssemblerTest(unittest.TestCase):
    def test_sps_pps_are_prepended_to_the_next_frame(self):
        assembler = FrameAssembler()
        for nal in (SPS, PPS):
            self.assertEqual(assembler.push(nal), [])
        self.assertEqual(assembler.push(IDR), [])
        self.assertEqual(assembler.flush(), (True, [SPS, PPS, IDR]))

    def test_a_following_vcl_closes_the_frame(self):
        assembler = FrameAssembler()
        for nal in (SPS, PPS, IDR):
            assembler.push(nal)
        self.assertEqual(assembler.push(DELTA), [(True, [SPS, PPS, IDR])])
        self.assertEqual(assembler.flush(), (False, [DELTA]))

    def test_aud_starts_a_new_frame(self):
        assembler = FrameAssembler()
        for nal in (SPS, PPS, IDR):
            assembler.push(nal)
        aud = bytes([0x09, 0xF0])
        self.assertEqual(assembler.push(aud), [(True, [SPS, PPS, IDR])])
        self.assertEqual(assembler.flush(), None)
        assembler.push(SPS)
        assembler.push(DELTA)
        self.assertEqual(assembler.flush(), (False, [aud, SPS, DELTA]))

    def test_non_vcl_after_a_vcl_stays_in_the_frame(self):
        assembler = FrameAssembler()
        assembler.push(IDR)
        sei = bytes([0x06, 0x01])
        assembler.push(sei)
        self.assertEqual(assembler.flush(), (True, [IDR, sei]))

    def test_flush_without_a_frame(self):
        self.assertIsNone(FrameAssembler().flush())

    def test_reset_drops_pending_nals(self):
        assembler = FrameAssembler()
        assembler.push(SPS)
        assembler.push(IDR)
        assembler.reset()
        assembler.push(DELTA)
        self.assertEqual(assembler.flush(), (False, [DELTA]))


class GopBufferTest(unittest.TestCase):
    def test_deltas_before_a_keyframe_are_not_cached(self):
        gop = GopBuffer()
        self.assertFalse(gop.add(b"delta", False))
        self.assertEqual(gop.messages(), [])
        self.assertEqual(len(gop), 0)

    def test_keyframe_starts_a_new_cache(self):
        gop = GopBuffer()
        gop.add(b"key", True)
        gop.add(b"delta", False)
        self.assertEqual(gop.messages(), [(True, b"key"), (False, b"delta")])
        gop.add(b"key2", True)
        self.assertEqual(gop.messages(), [(True, b"key2")])

    def test_clear(self):
        gop = GopBuffer()
        gop.add(b"key", True)
        gop.clear()
        self.assertEqual(len(gop), 0)
        self.assertFalse(gop.add(b"delta", False))

    def test_overflow_drops_the_whole_cache(self):
        gop = GopBuffer(max_frames=2)
        gop.add(b"key", True)
        self.assertTrue(gop.add(b"delta1", False))
        self.assertFalse(gop.add(b"delta2", False))
        self.assertEqual(gop.messages(), [])

    def test_messages_is_a_copy(self):
        gop = GopBuffer()
        gop.add(b"key", True)
        gop.messages().append((False, b"delta"))
        self.assertEqual(len(gop), 1)


class FindLastIdrTest(TempFileMixin, unittest.TestCase):
    def setUp(self):
        self.data = SAMPLE.read_bytes()

    def test_fixture_offset(self):
        self.assertEqual(find_last_idr(str(SAMPLE)), self.data.rindex(START + IDR))

    def test_window_starts_at_the_last_idr(self):
        tail = self.data[self.data.rindex(START + IDR):]
        self.assertEqual(
            find_last_idr(str(SAMPLE), window=len(tail)),
            self.data.rindex(START + IDR),
        )

    def test_no_idr(self):
        path = self.write_temp(START + SPS + START + PPS + START + DELTA)
        self.assertIsNone(find_last_idr(path))

    def test_missing_file(self):
        self.assertIsNone(find_last_idr("/nonexistent/sample.h264"))


if __name__ == "__main__":
    unittest.main()
