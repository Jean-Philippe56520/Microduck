"""No real camera, motor or WebRTC use; checklist is planning only."""
import unittest
from microduck_companion.oem_frame_preflight import (
    CaptureChecklist, evaluate_capture_preflight,
)

class CaptureChecklistTests(unittest.TestCase):
    def test_default_is_blocked(self):
        r=evaluate_capture_preflight(CaptureChecklist(),now_s=100.)
        self.assertEqual(r.status,"blocked")
        self.assertEqual(len(r.missing),6)
        self.assertEqual(r.frames_requested,0)
        self.assertFalse(r.transport_connected)
        self.assertFalse(r.sensor_authenticated)

    def test_all_claims_are_still_not_authentication(self):
        r=evaluate_capture_preflight(
            CaptureChecklist(True,True,True,True,True,True),
            now_s=100.,last_attempt_s=90.)
        self.assertEqual(r.status,"declared_checks_only_no_capture_authorized")
        self.assertFalse(r.sensor_authenticated)
        self.assertEqual(r.frames_requested,0)
        self.assertEqual(r.motor_commands_issued,0)

    def test_minimum_capture_interval(self):
        r=evaluate_capture_preflight(
            CaptureChecklist(True,True,True,True,True,True),
            now_s=100.,last_attempt_s=99.)
        self.assertIn("planned_minimum_interval",r.missing)

    def test_invalid_clock_and_claims(self):
        for t in (-1.,True,float("nan"),float("inf")):
            with self.assertRaises(ValueError):
                evaluate_capture_preflight(CaptureChecklist(),now_s=t)
        with self.assertRaises(ValueError):
            evaluate_capture_preflight(
                CaptureChecklist(operator_opt_in=1),now_s=100.)
        with self.assertRaises(ValueError):
            evaluate_capture_preflight(
                CaptureChecklist(),now_s=100.,last_attempt_s=105.)

if __name__=="__main__":
    unittest.main()
