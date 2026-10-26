"""F6-A: offline OEM inventory and conditional Yocto data-mount preflight.

No real robot, sockets, service installation, filesystem writes or inference.
All board and mountinfo samples are purely fictional local fixtures.
"""
from __future__ import annotations

from dataclasses import replace
import json
import unittest

from microduck_companion.embedded_readiness import (
    BoardInspection, EmbeddedPreparation, OEM_INTERFACES, OFFLINE_FUNCTIONS,
    OPTIONAL_PC_ONLY, SQLITE_PATH_CANDIDATE, StorageInspection,
    VOLATILE_SQLITE, YOCTO_SNAPSHOT_REVISION,
    inspect_claimed_board, inspect_data_mount,
    inspect_embedded_preparation, oem_manifest,
)
from microduck_companion.passive_sources import (
    OEM_API_VERSION, PINNED_OEM_REVISION,
)

DATA_SOURCE = "/dev/mmcblk0p5"
LINE = (
    "52 19 179:5 / /var/lib/robot rw,relatime - "
    "ext4 /dev/mmcblk0p5 rw,noatime\n"
)
UNRELATED = "25 1 179:2 / / rw,relatime - ext4 /dev/mmcblk0p2 rw\n"


class OemManifestTests(unittest.TestCase):
    def test_exact_pinned_contract_and_no_live_connection(self):
        result = oem_manifest()
        self.assertEqual(PINNED_OEM_REVISION, result["oem_daemon_revision_pinned"])
        self.assertEqual(OEM_API_VERSION, result["oem_api_version_documented"])
        self.assertEqual("91691234f3b518a94ee4391f8567c9486335f507",
                         YOCTO_SNAPSHOT_REVISION)
        self.assertEqual(3, len(result["interfaces"]))
        self.assertFalse(result["hardware_validated"])
        seen = {x["service"]: x for x in result["interfaces"]}
        self.assertEqual(
            {"robotd", "mediad", "tofd"}, set(seen),
        )
        self.assertEqual("/run/robotd.sock", seen["robotd"]["socket"])
        self.assertEqual("/run/mediad/media.sock",seen["mediad"]["socket"])
        self.assertEqual("/run/tofd/tof.sock", seen["tofd"]["socket"])
        self.assertEqual(("hello",),seen["mediad"]["implemented_read_methods"])
        self.assertEqual((),seen["robotd"]["implemented_read_methods"])
        self.assertEqual((),seen["tofd"]["implemented_read_methods"])
        self.assertIn("robot.health",seen["robotd"]["documented_read_methods"])
        self.assertIn("robot.subscribe",seen["robotd"]["documented_read_methods"])
        self.assertIn("tof.stream",seen["tofd"]["documented_read_methods"])
        for entry in seen.values():
            self.assertFalse(entry["connected"])
            self.assertFalse(entry["actuator_access_enabled"])
            self.assertNotIn("robot.move", entry["implemented_read_methods"])
            self.assertNotIn("robot.head", entry["implemented_read_methods"])

    def test_minimal_offline_functions_and_optional_pc_separate(self):
        manifest = oem_manifest()
        self.assertIn("local_motivations_and_intentions",OFFLINE_FUNCTIONS)
        self.assertIn("stationary_silent_default",OFFLINE_FUNCTIONS)
        self.assertNotIn("ollama_qwen_hypotheses",OFFLINE_FUNCTIONS)
        self.assertEqual(("ollama_qwen_hypotheses",),OPTIONAL_PC_ONLY)
        self.assertEqual(
            "mock_passive_events",
            manifest["offline_functions_fixture_only"][0],
        )
        self.assertIn("live_mediad_categories",
                      manifest["not_implemented_on_hardware"])
        self.assertIn("motion_intent_adapter",
                      manifest["not_implemented_on_hardware"])
        self.assertIn("systemd_companion_installation",
                      manifest["not_implemented_on_hardware"])

    def test_oem_interface_cannot_claim_actuator_authority(self):
        from microduck_companion.embedded_readiness import OemInterface
        with self.assertRaises(ValueError):
            OemInterface("motor", "/run/robotd.sock",
                         ("robot.move",),("robot.move",),True)
        with self.assertRaises(ValueError):
            OemInterface("mediad", "/tmp/fake.sock",("hello",),("hello",))
        with self.assertRaises(ValueError):
            OemInterface("mediad","/run/fake.sock",("hello",),("media.frame",))


class BoardTests(unittest.TestCase):
    def test_supported_claimed_boards_are_not_hardware_evidence(self):
        for machine,compatible in (
            ("microduck-zero3","radxa,zero3w-aic8800ds2"),
            ("microduck-beta","pollen,microduck-beta"),
        ):
            with self.subTest(machine=machine):
                result = inspect_claimed_board(machine,compatible)
                self.assertEqual("claimed_family_match",result.status)
                self.assertEqual(machine,result.machine)
                self.assertFalse(result.physically_verified)

    def test_missing_unsupported_crosswired_and_factory_claims_fail_closed(self):
        cases=(
            (None,None,"unknown"),
            ("microduck-beta",None,"unknown"),
            (None,"pollen,microduck-beta","unknown"),
            ("microduck-beta","radxa,zero3w-aic8800ds2",
             "mismatch_or_unsupported"),
            ("microduck-zero3","pollen,microduck-beta",
             "mismatch_or_unsupported"),
            ("microduck-beta","seeed,microduck",
             "mismatch_or_unsupported"),
            ("microduck-v2","pollen,microduck-beta",
             "mismatch_or_unsupported"),
            ("microduck-beta","pollen,microduck-beta\x00other",
             "mismatch_or_unsupported"),
        )
        for machine,compatible,status in cases:
            with self.subTest(machine=machine,compatible=compatible):
                result=inspect_claimed_board(machine,compatible)
                self.assertEqual(status,result.status)
                self.assertFalse(result.physically_verified)

    def test_invalid_type_and_forced_hardware_verified_refused(self):
        for bad in (True,1,[],{},("microduck-beta",)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                inspect_claimed_board(bad,None)
        with self.assertRaises(ValueError):
            replace(inspect_claimed_board(None,None),
                    physically_verified=True)


class StorageTests(unittest.TestCase):
    def test_mount_absent_or_directory_only_never_enables_persistence(self):
        for data in ("",UNRELATED,"/var/lib/robot",
                     "52 19 179:5 / /var/lib/robot"):
            with self.subTest(data=data):
                status=inspect_data_mount(data,partlabel_device=DATA_SOURCE)
                self.assertIn(status.status,
                              {"mount_missing","malformed_data_mount"})
                self.assertIsNone(status.sqlite_candidate)
                self.assertEqual(VOLATILE_SQLITE,status.sqlite_selected)
                self.assertFalse(status.hardware_validated)

    def test_ext4_partlabel_claim_only_yields_candidate_not_sqlite_selection(self):
        state=inspect_data_mount(UNRELATED+LINE,
                                 partlabel_device=DATA_SOURCE)
        self.assertEqual("persistent_mount_candidate",state.status)
        self.assertEqual(SQLITE_PATH_CANDIDATE,state.sqlite_candidate)
        self.assertEqual(":memory:",state.sqlite_selected)
        self.assertFalse(state.hardware_validated)

    def test_mount_without_verified_device_never_enables_candidate(self):
        state=inspect_data_mount(LINE)
        self.assertEqual("partlabel_unconfirmed",state.status)
        self.assertIsNone(state.sqlite_candidate)

    def test_wrong_source_cannot_be_trusted_as_data(self):
        state=inspect_data_mount(LINE,
                                 partlabel_device="/dev/mmcblk0p6")
        self.assertEqual("source_mismatch",state.status)
        self.assertIsNone(state.sqlite_candidate)

    def test_readonly_mount_is_rejected(self):
        bad=LINE.replace("rw,relatime","ro,relatime")
        state=inspect_data_mount(bad,partlabel_device=DATA_SOURCE)
        self.assertEqual("not_writable_mount",state.status)

    def test_root_fstype_overlay_and_bind_subdir_rejected(self):
        variants=(
            LINE.replace("ext4 /dev/mmcblk0p5","overlay /dev/mmcblk0p5"),
            LINE.replace("179:5 / /var/lib/robot","179:5 /data /var/lib/robot"),
            LINE.replace("179:5 / /var/lib/robot","179:5 / /var/lib/robot2"),
        )
        statuses=("not_data_ext4","not_data_ext4","mount_missing")
        for wire,expected in zip(variants,statuses):
            with self.subTest(expected=expected):
                self.assertEqual(expected,inspect_data_mount(
                    wire,partlabel_device=DATA_SOURCE).status)

    def test_duplicate_data_mount_is_ambiguous(self):
        state=inspect_data_mount(LINE+LINE,partlabel_device=DATA_SOURCE)
        self.assertEqual("ambiguous_mounts",state.status)

    def test_invalid_mountinfo_body_is_refused(self):
        from microduck_companion.embedded_readiness import MAX_MOUNTINFO_CHARS
        with self.assertRaises(TypeError):
            inspect_data_mount(None)
        for txt in (
            "x"* (MAX_MOUNTINFO_CHARS+1),
            UNRELATED*600,
        ):
            with self.subTest(length=len(txt)):
                self.assertEqual("oversized_mountinfo",
                                 inspect_data_mount(txt).status)

    def test_invalid_claimed_device_is_refused(self):
        for value in (
            "mmcblk0p5", "/etc/passwd", "/dev/../../tmp",
            "/dev/mmcblk0p5//", "/dev/mmcblk0p5/../x",
            "/dev/mmcblk0p5 ", "/dev/disk?root",
            "/dev/" + "a"*200,
        ):
            with self.subTest(value=value):
                status=inspect_data_mount(LINE,partlabel_device=value)
                # /etc path does not pass, /dev fragments with '..' do not pass
                self.assertEqual("invalid_partlabel_claim",status.status)

    def test_escaped_mountpoint_is_not_claimed_as_data(self):
        # mountinfo uses \040 for an actual space; an encoded path is not
        # silently decoded, nor promoted to the canonical /var/lib/robot.
        line=LINE.replace("/var/lib/robot","/var/lib/robot\\040old")
        self.assertEqual("mount_missing",inspect_data_mount(
            line,partlabel_device=DATA_SOURCE).status)

    def test_cannot_force_a_selected_persistent_database(self):
        good=inspect_data_mount(LINE,partlabel_device=DATA_SOURCE)
        with self.assertRaises(ValueError):
            replace(good,sqlite_selected=SQLITE_PATH_CANDIDATE)
        with self.assertRaises(ValueError):
            replace(good,hardware_validated=True)
        with self.assertRaises(ValueError):
            StorageInspection("persistent_mount_candidate",
                              sqlite_candidate="/tmp/identity.sqlite3")


class PreparationTests(unittest.TestCase):
    def test_no_input_means_still_offline_and_not_installed(self):
        p=inspect_embedded_preparation()
        self.assertEqual("offline_fixture_only",p.mode)
        self.assertEqual("unknown",p.board.status)
        self.assertEqual("mount_missing",p.storage.status)
        self.assertFalse(p.pc_required)
        self.assertFalse(p.navigation_authorized)
        self.assertFalse(p.installation_authorized)
        self.assertFalse(p.live_sensor_authenticated)
        self.assertFalse(p.robot_hardware_validated)
        self.assertEqual(0,p.oem_sockets_contacted)
        self.assertEqual(0,p.motor_commands_issued)
        self.assertEqual(0,p.speaker_commands_issued)

    def test_even_positive_claims_are_not_permission_to_connect_or_move(self):
        p=inspect_embedded_preparation(
            machine="microduck-beta",
            compatible="pollen,microduck-beta",
            mountinfo_text=LINE,
            partlabel_device=DATA_SOURCE,
        )
        self.assertEqual("claimed_family_match",p.board.status)
        self.assertEqual("persistent_mount_candidate",p.storage.status)
        self.assertEqual(":memory:",p.storage.sqlite_selected)
        self.assertFalse(p.installation_authorized)
        self.assertFalse(p.navigation_authorized)
        self.assertEqual(0,p.oem_sockets_contacted)

    def test_attempts_to_promote_fixture_to_real_io_are_refused(self):
        p=inspect_embedded_preparation()
        for change in (
            {"pc_required":True},
            {"mode":"live"},
            {"oem_sockets_contacted":1},
            {"motor_commands_issued":1},
            {"speaker_commands_issued":1},
            {"live_sensor_authenticated":True},
            {"navigation_authorized":True},
            {"installation_authorized":True},
            {"robot_hardware_validated":True},
        ):
            with self.subTest(change=change),self.assertRaises(ValueError):
                replace(p,**change)

    def test_json_serializable_report_does_not_embed_secrets(self):
        p=inspect_embedded_preparation()
        report={
            "manifest":oem_manifest(),
            "mode":p.mode,
            "board_status":p.board.status,
            "storage_status":p.storage.status,
            "hardware_validated":p.robot_hardware_validated,
        }
        text=json.dumps(report)
        for sensitive in ("password","token","transcript","robot.move"):
            self.assertNotIn(sensitive,text.lower())


if __name__=="__main__":
    unittest.main()
