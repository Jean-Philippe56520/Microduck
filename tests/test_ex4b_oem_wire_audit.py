"""EX4-B: pinned OEM wire shapes, negative cases, and no physical causality."""
from __future__ import annotations

from dataclasses import asdict
import math
import unittest

from microduck_companion.ex4b_oem_wire_audit import (
    FIXTURE_SOURCE, OemWireFrame, OemWireProposal, PINNED_API_VERSION,
    PINNED_OEM_SHA, review_oem_wire_batch, review_oem_wire_fixture,
)


def packet(method="robot.do", *, request_id=11, params=None):
    if params is None:
        params = {
            "robot.do": {"skill": "kick_left"},
            "robot.look": {"x": .3, "y": 0., "z": 0., "neck_pitch": 0.},
            "robot.stop": None,
            "robot.move": {"vx": .1, "vy": 0., "vyaw": 0.},
            "robot.head": {
                "neck_pitch": 0., "head_pitch": 0.,
                "head_yaw": 0., "head_roll": 0.,
            },
        }[method]
    p = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        p["id"] = request_id
    if params is not None:
        p["params"] = params
    return p


def ack(*, accepted=True, request_id=11, reason=None):
    res = {"accepted": accepted}
    if reason is not None:
        res["reason"] = reason
    return OemWireFrame(12., {
        "jsonrpc": "2.0", "id": request_id, "result": res,
    })


def state(*, at=13., t=8., ns=8_000_000_000,
          limited=False, fallen=False, limp=False, picked_up=False,
          hz=50.):
    return OemWireFrame(at, {
        "jsonrpc": "2.0",
        "method": "robot.state",
        "params": {
            "t": t, "t_ns": ns,
            "move": {
                "requested": [.1, 0., 0.],
                "applied": [0. if limited else .1, 0., 0.],
                "limited_by": ["deadman"] if limited else [],
            },
            "policy": "walk",
            "safety": {
                "fallen": fallen, "limp": limp, "picked_up": picked_up,
            },
            "loop": {"hz": hz, "missed": 0},
        },
    })


def proposal(method="robot.do", *, request_id=11,
             session="s-0000000000000001", sequence=1, **kwargs):
    return OemWireProposal(
        session=session, sequence=sequence,
        sent_monotonic_s=10., packet=packet(method, request_id=request_id),
        **kwargs,
    )


def inspect(p=None, *, reply=None, states=(), now=15.):
    return review_oem_wire_fixture(
        p or proposal(), reply=reply, states=states, now_monotonic_s=now,
    )


class Ex4bOemWireAudit(unittest.TestCase):
    def assert_no_execution(self, result):
        self.assertEqual(FIXTURE_SOURCE, result.source)
        self.assertEqual("not_attested", result.authorized)
        self.assertEqual("not_attested", result.executed)
        self.assertFalse(result.physical_execution_verified)
        self.assertFalse(result.causality_established)
        self.assertFalse(result.physical_learning_allowed)
        self.assertEqual(0, result.motor_commands_issued)

    def test_pinned_api_context(self):
        self.assertEqual(44, PINNED_API_VERSION)
        self.assertEqual(40, len(PINNED_OEM_SHA))
        self.assert_no_execution(inspect())

    def test_accepted_skill_only_queued(self):
        verdict = inspect(reply=ack())
        self.assertEqual("queued_only", verdict.reply_status)
        self.assertEqual("not_observed", verdict.state_status)
        self.assert_no_execution(verdict)

    def test_accepted_skill_with_two_consistent_frames_is_not_executed(self):
        frames = (state(), state(at=14., t=8.2, ns=8_200_000_000))
        verdict = inspect(reply=ack(), states=frames)
        self.assertEqual("coherent_unlinked_telemetry", verdict.state_status)
        self.assertEqual("queued_only", verdict.reply_status)
        self.assert_no_execution(verdict)

    def test_refused_skill_is_not_executed(self):
        verdict = inspect(reply=ack(accepted=False, reason="policy not driving"))
        self.assertEqual("refused", verdict.reply_status)
        self.assert_no_execution(verdict)

    def test_skill_notification_has_no_ack(self):
        verdict = inspect(proposal(request_id=None))
        self.assertEqual("no_reply_expected", verdict.reply_status)
        self.assert_no_execution(verdict)
        with self.assertRaises(ValueError):
            inspect(proposal(request_id=None), reply=ack())

    def test_unknown_skill_name_not_promoted(self):
        p = proposal()
        p.packet["params"]["skill"] = "kick with spaces"
        with self.assertRaises(ValueError):
            inspect(p)

    def test_look_unclamped_only_computed_not_reached(self):
        p = proposal("robot.look")
        result = {
            "head": {
                "neck_pitch": 0., "head_pitch": .1, "head_yaw": .2,
                "head_roll": 0.,
            },
            "clamped": False,
        }
        reply = OemWireFrame(12., {
            "jsonrpc": "2.0", "id": 11, "result": result,
        })
        v = inspect(p, reply=reply, states=(state(),))
        self.assertEqual("target_computed_only", v.reply_status)
        self.assert_no_execution(v)

    def test_look_clamped_does_not_confirm_target(self):
        p = proposal("robot.look")
        reply = OemWireFrame(12., {
            "jsonrpc": "2.0", "id": 11,
            "result": {
                "head": {
                    "neck_pitch": 0., "head_pitch": 0.,
                    "head_yaw": 0., "head_roll": 0.,
                },
                "clamped": True,
            },
        })
        v = inspect(p, reply=reply)
        self.assertEqual("target_clamped_only", v.reply_status)
        self.assert_no_execution(v)

    def test_stop_accepted_is_not_global_motion_completion(self):
        v = inspect(proposal("robot.stop"), reply=ack())
        self.assertEqual("zero_velocity_requested_only", v.reply_status)
        self.assert_no_execution(v)

    def test_move_notification_no_reply_or_motor(self):
        v = inspect(proposal("robot.move", request_id=None), states=(state(),))
        self.assertEqual("no_reply_expected", v.reply_status)
        self.assert_no_execution(v)

    def test_move_request_ack_is_only_intent_received(self):
        v = inspect(proposal("robot.move"), reply=ack(), states=(state(),))
        self.assertEqual("intent_received_only", v.reply_status)
        self.assert_no_execution(v)

    def test_head_notification_is_not_measured_gaze(self):
        v = inspect(proposal("robot.head", request_id=None), states=(state(),))
        self.assertEqual("no_reply_expected", v.reply_status)
        self.assert_no_execution(v)

    def test_missing_reply_cannot_be_accepted(self):
        v = inspect(states=(state(),))
        self.assertEqual("no_reply", v.reply_status)
        self.assert_no_execution(v)

    def test_rpc_error_is_not_a_refusal_or_execution(self):
        p = proposal()
        error = OemWireFrame(12., {
            "jsonrpc": "2.0", "id": 11, "error": {
                "code": -32602, "message": "invalid parameters",
            },
        })
        v = inspect(p, reply=error)
        self.assertEqual("rpc_error", v.reply_status)
        self.assert_no_execution(v)

    def test_refusal_requires_reason(self):
        with self.assertRaises(ValueError):
            inspect(reply=ack(accepted=False))

    def test_unmatched_id_rejected(self):
        with self.assertRaises(ValueError):
            inspect(reply=ack(request_id=12))

    def test_id_type_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            inspect(reply=OemWireFrame(12., {
                "jsonrpc": "2.0", "id": "11", "result": {"accepted": True},
            }))

    def test_forged_execution_flag_rejected(self):
        bad = ack()
        bad.packet["result"]["executed"] = True
        with self.assertRaises(ValueError):
            inspect(reply=bad)

    def test_extra_top_level_claim_rejected(self):
        p = proposal()
        p.packet["verified_on_robot"] = True
        with self.assertRaises(ValueError):
            inspect(p)

    def test_invalid_api_or_source_rejected_at_constructor(self):
        for kw in (
            {"api_version": 45}, {"api_version": True},
            {"oem_sha": "a" * 40}, {"source": "robotd_authenticated"},
        ):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                proposal(**kw)

    def test_wrong_source_on_frame_rejected(self):
        with self.assertRaises(ValueError):
            OemWireFrame(12., {}, source="physical_robotd")

    def test_duplicate_frames_refused(self):
        with self.assertRaises(ValueError):
            inspect(reply=ack(), states=(state(), state(at=13., t=8., ns=8_000_000_000)))

    def test_out_of_order_local_frames_refused(self):
        with self.assertRaises(ValueError):
            inspect(reply=ack(), states=(state(at=14.), state(at=13., t=9., ns=9_000_000_000)))

    def test_reset_daemon_clock_refused_in_same_session(self):
        with self.assertRaises(ValueError):
            inspect(reply=ack(), states=(state(), state(at=14., t=2., ns=8_100_000_000)))

    def test_zero_ns_is_incomplete_only(self):
        v = inspect(reply=ack(), states=(state(ns=0),))
        self.assertEqual("incomplete_clock_unlinked_telemetry", v.state_status)
        self.assert_no_execution(v)

    def test_future_frame_refused(self):
        with self.assertRaises(ValueError):
            inspect(reply=ack(), states=(state(at=16.),))

    def test_stale_request_refused(self):
        with self.assertRaises(ValueError):
            inspect(now=41.)

    def test_reply_before_request_refused(self):
        with self.assertRaises(ValueError):
            inspect(reply=OemWireFrame(9., ack().packet))

    def test_limited_move_telemetry_stays_unlinked(self):
        v = inspect(reply=ack(), states=(state(limited=True),))
        self.assertEqual("limited_unlinked_telemetry", v.state_status)
        self.assert_no_execution(v)

    def test_fallen_or_limp_or_pickup_state_is_unsafe(self):
        for kw in ({"fallen": True}, {"limp": True}, {"picked_up": True}):
            with self.subTest(kw=kw):
                v = inspect(reply=ack(), states=(state(**kw),))
                self.assertEqual("unsafe_unlinked_telemetry", v.state_status)
                self.assert_no_execution(v)

    def test_state_with_forged_completed_field_refused(self):
        frame = state()
        frame.packet["params"]["completed"] = True
        with self.assertRaises(ValueError):
            inspect(reply=ack(), states=(frame,))

    def test_wrong_method_notification_refused(self):
        frame = state()
        frame.packet["method"] = "robot.complete"
        with self.assertRaises(ValueError):
            inspect(reply=ack(), states=(frame,))

    def test_bad_loop_and_nonfinite_numeric_rejected(self):
        for bad in (float("nan"), float("inf"), -1):
            with self.subTest(bad=bad):
                frame = state()
                frame.packet["params"]["loop"]["hz"] = bad
                with self.assertRaises(ValueError):
                    inspect(reply=ack(), states=(frame,))

    def test_oem_nanosecond_and_missed_counters_are_uint64(self):
        frame = state(ns=2**63)
        frame.packet["params"]["loop"]["missed"] = 2**63
        v = inspect(reply=ack(), states=(frame,))
        self.assertEqual("coherent_unlinked_telemetry", v.state_status)
        self.assert_no_execution(v)

    def test_oem_nanosecond_overflow_and_boolean_rejected(self):
        for bad in (2**64, -1, True):
            with self.subTest(value=bad):
                frame = state(ns=bad)
                with self.assertRaises(ValueError):
                    inspect(reply=ack(), states=(frame,))

    def test_excessive_frames_refused(self):
        with self.assertRaises(ValueError):
            inspect(reply=ack(), states=tuple(state(at=13. + i/10, t=8 + i/10, ns=8_000_000_000+i*100_000_000) for i in range(9)))

    def test_unsupported_or_malicious_method_refused(self):
        p = proposal()
        p.packet["method"] = "robot.rebootMotors"
        with self.assertRaises(ValueError):
            inspect(p)

    def test_infinite_or_boolean_move_value_refused(self):
        p = proposal("robot.move", request_id=None)
        for value in (float("nan"), float("inf"), True):
            p.packet["params"]["vx"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                inspect(p)

    def test_look_as_notification_refused(self):
        p = proposal("robot.look", request_id=None)
        with self.assertRaises(ValueError):
            inspect(p)

    def test_batch_distinct_cycles_without_storing(self):
        exchanges = (
            (proposal(sequence=1, request_id=11), ack(), (state(),)),
            (proposal(sequence=2, request_id=12), ack(request_id=12), ()),
        )
        results = review_oem_wire_batch(exchanges, now_monotonic_s=15.)
        self.assertEqual(2, len(results))
        for v in results:
            self.assert_no_execution(v)

    def test_batch_duplicate_cycle_rejected(self):
        p = proposal()
        with self.assertRaises(ValueError):
            review_oem_wire_batch(((p, ack(), ()), (p, ack(), ())), now_monotonic_s=15.)

    def test_batch_rpc_reuse_rejected(self):
        entries = (
            (proposal(sequence=1, request_id=11), ack(), ()),
            (proposal(sequence=2, request_id=11), ack(), ()),
        )
        with self.assertRaises(ValueError):
            review_oem_wire_batch(entries, now_monotonic_s=15.)

    def test_serialized_verdict_cannot_promote_itself(self):
        v = asdict(inspect(reply=ack(), states=(state(),)))
        self.assertFalse(v["physical_execution_verified"])
        self.assertFalse(v["physical_learning_allowed"])
        self.assertEqual("not_attested", v["executed"])
        self.assertNotIn("reward", v)


if __name__ == "__main__":
    unittest.main()
