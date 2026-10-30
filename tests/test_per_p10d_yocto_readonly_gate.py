"""PER-P10D negative tests: source agreement never proves an installed robot image."""
import tempfile
import unittest
from pathlib import Path

from scripts.per_p10d_yocto_readonly_gate import (
    BLOBS, PIN, YoctoGateRefused, audit_checkout, audit_texts,
)

RECIPE = """
if not d.getVar("MICRODUCK_DAEMON_VERSION") or not d.getVar("MICRODUCK_DAEMON_SRCREV"):
    raise bb.parse.SkipRecipe("missing version")
SRC_URI = "git://git@github.com/pollen-robotics/microduck_daemon.git;protocol=ssh"
SRCREV_daemon = "${MICRODUCK_DAEMON_SRCREV}"
CARGO_BUILD_FLAGS += "--workspace --exclude xtask --exclude test-support --exclude duckctl --exclude duck-ether"
DEPENDS += "glib-2.0 gstreamer1.0 gstreamer1.0-plugins-base gstreamer1.0-plugins-bad"
RDEPENDS:${PN} += "gstreamer1.0-plugins-rs gstreamer1.0-rockchip"
RRECOMMENDS:${PN}:append:aarch64 = " onnxruntime"
SYSTEMD_SERVICE:${PN} = "mediad.service"
install -d ${D}/opt/robot/daemon/releases/${PV}/bin
"""

ORT = """
COMPATIBLE_HOST = "aarch64.*-linux"
SRC_URI = "https://github.com/microsoft/onnxruntime/releases/download/v${PV}/onnxruntime-linux-aarch64-${PV}.tgz"
SRC_URI[sha256sum] = "e15ff8b5d85afe6c144d97c6fd432254bf76a219daaf17658087d6ecb3e8f0bb"
install -m 0755 ${S}/lib/libonnxruntime.so.${PV}
"""

KAS = """
target: microduck-image-dev
env:
  MICRODUCK_DAEMON_VERSION: null
  MICRODUCK_DAEMON_SRCREV: null
"""


class P10DYoctoSafetyTests(unittest.TestCase):
    def test_source_contract_always_marks_deployment_blocked(self):
        result = audit_texts(RECIPE, ORT, KAS)
        self.assertEqual(result["status"], "source_contract_ok_deployment_blocked")
        self.assertFalse(result["bitbake_run"])
        self.assertFalse(result["yocto_image_created"])
        self.assertFalse(result["companion_overlays_in_recipe"])
        self.assertEqual(result["ort_aarch64"],
                         "recipe_present_but_only_rrecommended")
        self.assertEqual(len(PIN), 40)
        self.assertEqual(len(BLOBS), 3)

    def test_missing_release_guards_are_rejected(self):
        variants = [
            (RECIPE.replace('d.getVar("MICRODUCK_DAEMON_SRCREV")',
                            'd.getVar("AUTOREV")'), ORT, KAS),
            (RECIPE.replace('SRCREV_daemon = "${MICRODUCK_DAEMON_SRCREV}"',
                            'SRCREV_daemon = "${AUTOREV}"'), ORT, KAS),
            (RECIPE, ORT, KAS.replace("MICRODUCK_DAEMON_VERSION: null",
                                      "MICRODUCK_DAEMON_VERSION: unreleased")),
            (RECIPE.replace("--exclude duckctl", "--exclude mediad"), ORT, KAS),
        ]
        for recipe, ort, kas in variants:
            with self.subTest(example=recipe[-80:]):
                with self.assertRaises(YoctoGateRefused):
                    audit_texts(recipe, ort, kas)

    def test_inconsistent_runtime_and_unlicensed_model_changes_are_rejected(self):
        variants = [
            (RECIPE.replace("RRECOMMENDS:${PN}:append:aarch64",
                            "RDEPENDS:${PN}:append:aarch64"), ORT, KAS),
            (RECIPE + 'file://kwipi_seg.rknn', ORT, KAS),
            (RECIPE.replace("gstreamer1.0-plugins-rs", "gstreamer1.0-stub"),
             ORT, KAS),
            (RECIPE, ORT.replace("e15ff8b5", "00000000"), KAS),
            (RECIPE, ORT.replace("libonnxruntime.so.${PV}",
                                 "libfakeonnxruntime.so.${PV}"), KAS),
        ]
        for recipe, ort, kas in variants:
            with self.subTest(example=recipe[-80:]):
                with self.assertRaises(YoctoGateRefused):
                    audit_texts(recipe, ort, kas)

    def test_unmarked_folder_and_symlink_cannot_claim_pinned_oem_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(YoctoGateRefused):
                audit_checkout(root)
            (root / ".git").mkdir()
            with self.assertRaises(Exception):
                audit_checkout(root)
            link = root.parent / (root.name + "-p10d-link")
            link.symlink_to(root, target_is_directory=True)
            try:
                with self.assertRaises(YoctoGateRefused):
                    audit_checkout(link)
            finally:
                link.unlink()


if __name__ == "__main__":
    unittest.main()
