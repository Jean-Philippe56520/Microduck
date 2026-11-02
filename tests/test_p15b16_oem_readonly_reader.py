"""P15-B16: fail-closed public OEM reader; no real /run used in tests."""
import unittest
from unittest.mock import patch

from microduck_companion.b16_oem_readonly_reader import (
    B16OEMDetectionReader, B16ReadResult, B16Refused,
)


class B16ReaderContractTests(unittest.TestCase):
    def test_default_is_inert(self):
        with patch("microduck_companion.b16_oem_readonly_reader._checked_once",
                   side_effect=AssertionError("unexpected OEM contact")):
            self.assertEqual(B16OEMDetectionReader().read().status,
                             "disabled_no_oem_contact")

    def test_invalid_parameters_refused(self):
        for opt in ({"enabled":1}, {"timeout_s":1}, {"timeout_s":float("nan")},
                    {"timeout_s":0}, {"timeout_s":True}):
            with self.subTest(opt=opt), self.assertRaises(ValueError):
                B16OEMDetectionReader(**opt)

    def test_nonroot_fixture_cannot_open_arbitrary_root(self):
        from pathlib import Path
        from microduck_companion.b12_local_wire_contract import B12LocalSequenceGate
        from microduck_companion.b16_oem_readonly_reader import _checked_once
        with self.assertRaises(B16Refused):
            _checked_once(Path("/tmp/other"), mediad_uid=31052,
                          mediad_gid=31064, kwipi_uid=31053,
                          kwipi_gid=31062, robot_gid=31061,
                          sequence_gate=B12LocalSequenceGate(), timeout_s=.1)

    def test_explicit_reader_only_returns_bounded_claim_and_rate_limits(self):
        receipt=B16ReadResult("oem_identity_and_b12_claim_consistent_not_sensor",
                             reported_boxes=1, look_seq=1)
        with patch("microduck_companion.b16_oem_readonly_reader._observer_ids",
                   return_value=(31052,31064,31053,31062,31061)), \
             patch("microduck_companion.b16_oem_readonly_reader._checked_once",
                   return_value=receipt) as called:
            reader=B16OEMDetectionReader(enabled=True)
            result=reader.read()
            self.assertEqual(result.category,"unknown")
            self.assertFalse(result.verified_sensor)
            self.assertFalse(result.executable_verified)
            self.assertEqual((result.media_bytes_stored,result.memory_writes,
                              result.motor_commands_issued),(0,0,0))
            self.assertEqual(reader.read().status,"rate_limited")
            called.assert_called_once()

    def test_failure_is_not_promoted(self):
        with patch("microduck_companion.b16_oem_readonly_reader._observer_ids",
                   side_effect=B16Refused("absent")):
            self.assertEqual(B16OEMDetectionReader(enabled=True).read().status,
                             "unavailable_or_refused")


if __name__=="__main__":
    unittest.main()
