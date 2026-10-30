"""Read-only PER-P10D Yocto source provenance: positive and negative gates.

Real sources come from exact-sha checkouts. No BitBake, model, board or
recipe modifications are performed.
"""
from __future__ import annotations

import os
from pathlib import Path
import unittest

from scripts.per_p10d_yocto_source_gate import (
    BLOCKED, ContractRefused, read_pinned_sources, validate_contract,
)


class P10DPinnedYoctoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.yocto = Path(os.environ["KWIPI_P10D_YOCTO_ROOT"])
        cls.oem = Path(os.environ["KWIPI_P10D_OEM_ROOT"])
        cls.original = read_pinned_sources(cls.yocto, cls.oem)

    def check_negative(self, key: str, before: str, after: str) -> None:
        self.assertEqual(self.original[key].count(before), 1)
        changed = self.original.copy()
        changed[key] = changed[key].replace(before, after)
        with self.assertRaises(ContractRefused):
            validate_contract(changed)

    def test_real_pinned_recipes_explicitly_block_deployment(self):
        report = validate_contract(self.original)
        self.assertEqual(report["status"], BLOCKED)
        self.assertEqual(report["full_mediad_package"],
                         "OEM_release_only_not_Companion_overlay")
        self.assertFalse(report["yocto_image_built"])
        self.assertFalse(report["physical_robot_validated"])
        self.assertFalse(report["kwipi_detection_enabled_by_default"])
        self.assertEqual(report["motor_commands_issued"], 0)

    def test_broken_yocto_pin_and_unavailable_sources_fail_closed(self):
        with self.assertRaises(ContractRefused):
            read_pinned_sources(self.oem, self.oem)
        with self.assertRaises((OSError, ContractRefused)):
            read_pinned_sources(self.yocto / "not-present", self.oem)
        with self.assertRaises(ContractRefused):
            validate_contract({"daemon": self.original["daemon"]})

    def test_missing_gstreamer_or_mediad_build_breaks_gate(self):
        self.check_negative(
            "daemon",
            'DEPENDS += "glib-2.0 gstreamer1.0 gstreamer1.0-plugins-base gstreamer1.0-plugins-bad"',
            'DEPENDS += "glib-2.0"',
        )
        self.check_negative(
            "daemon",
            'CARGO_BUILD_FLAGS += "--workspace --exclude xtask --exclude test-support --exclude duckctl --exclude duck-ether"',
            'CARGO_BUILD_FLAGS += "--workspace --exclude mediad"',
        )

    def test_onnx_as_hard_dependence_or_removed_recommendation_is_not_current_source(self):
        self.check_negative(
            "daemon",
            'RRECOMMENDS:${PN}:append:aarch64 = " onnxruntime"',
            'RDEPENDS:${PN}:append:aarch64 = " onnxruntime"',
        )
        self.check_negative(
            "daemon",
            'RRECOMMENDS:${PN}:append:aarch64 = " onnxruntime"',
            '# onnxruntime not selected',
        )

    def test_no_autorev_nor_unpinned_daemon_or_missing_source(self):
        self.check_negative(
            "daemon",
            'SRCREV_daemon = "${MICRODUCK_DAEMON_SRCREV}"',
            'SRCREV_daemon = "${AUTOREV}"',
        )
        self.check_negative(
            "daemon",
            'git://git@github.com/pollen-robotics/microduck_daemon.git',
            'git://git@github.com/example/unknown.git',
        )
        self.check_negative(
            "kas",
            'MICRODUCK_DAEMON_SRCREV: null',
            'MICRODUCK_DAEMON_SRCREV: "${AUTOREV}"',
        )

    def test_wrong_onnx_sha_or_platform_cannot_pass(self):
        self.check_negative(
            "onnx",
            'SRC_URI[sha256sum] = "e15ff8b5d85afe6c144d97c6fd432254bf76a219daaf17658087d6ecb3e8f0bb"',
            'SRC_URI[sha256sum] = "bad"',
        )
        self.check_negative(
            "onnx",
            'COMPATIBLE_HOST = "aarch64.*-linux"',
            'COMPATIBLE_HOST = "x86_64.*-linux"',
        )

    def test_unsafe_oem_default_or_fallback_is_refused(self):
        self.check_negative(
            "params",
            "impl Default for DuckDetectorParams {\n"
            "    fn default() -> Self {\n"
            "        Self {\n"
            "            enabled: false,",
            "impl Default for DuckDetectorParams {\n"
            "    fn default() -> Self {\n"
            "        Self {\n"
            "            enabled: true,",
        )
        self.check_negative(
            "params",
            'return vec![path.clone()];',
            'return DETECTOR_FILES.iter().map(PathBuf::from).collect();',
        )

    def test_oem_recipe_does_not_secretly_install_companion_overlay(self):
        changed = self.original.copy()
        changed["daemon"] += "\n# install per_p10c_kwipi_seg.rknn automatically\n"
        with self.assertRaises(ContractRefused):
            validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
