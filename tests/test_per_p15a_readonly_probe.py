"""P15A source/fixture tests. No robot, BitBake, rootfs, or hardware used."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import socket
import tempfile
import threading
import sys
import unittest

from scripts.per_p14a_embedded_wheel import current_source
from microduck_companion.sim_ipc import TelemetryTimeout

ROOT = Path(__file__).resolve().parents[1]
LAYER = ROOT / "yocto/meta-kwipi-p15-readonly"
RECIPE_BASE = LAYER / "recipes-kwipi/kwipi-readonly-probe"
SCRIPT = RECIPE_BASE / "files/health_probe.py"
UNIT = RECIPE_BASE / "files/kwipi-readonly-probe.service"
RECIPE = RECIPE_BASE / "kwipi-readonly-probe_0.1.bb"
DEV_APPEND = LAYER / "recipes-core/images/microduck-image-dev.bbappend"

spec = importlib.util.spec_from_file_location("kwipi_p15_health_probe", SCRIPT)
assert spec is not None and spec.loader is not None
health_probe = importlib.util.module_from_spec(spec)
old_dont_write_bytecode = sys.dont_write_bytecode
try:
    # The global unittest suite imports modules before running tests. Avoid
    # producing an untracked .pyc inside the five-file Yocto source layer.
    sys.dont_write_bytecode = True
    spec.loader.exec_module(health_probe)
finally:
    sys.dont_write_bytecode = old_dont_write_bytecode


class SingleResponseDaemon:
    """Only a fake read-only IPC endpoint, never a robot controller."""

    def __init__(self, directory, response):
        self.path = str(Path(directory) / "robotd-test.sock")
        self.response = response
        self.requests = []
        self.errors = []
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.settimeout(2.0)
        self.server.bind(self.path)
        self.server.listen(1)
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        try:
            conn, _ = self.server.accept()
            with conn:
                conn.settimeout(1.0)
                data = b""
                while b"\n" not in data:
                    data += conn.recv(4096)
                    if len(data) > 4096:
                        raise AssertionError("unexpected oversized request")
                request = json.loads(data.split(b"\n", 1)[0])
                self.requests.append(request)
                conn.sendall((json.dumps({
                    "jsonrpc": "2.0",
                    "id": request["id"],
                    "result": self.response,
                }) + "\n").encode("utf-8"))
        except BaseException as exc:
            self.errors.append(exc)
        finally:
            self.server.close()

    def finish(self):
        self.thread.join(timeout=3.0)
        if self.thread.is_alive():
            raise AssertionError("fake daemon still running")
        if self.errors:
            raise self.errors[0]


class P15AReadOnlyHealthTests(unittest.TestCase):
    def test_real_fixture_sends_only_one_oem_health_request(self):
        with tempfile.TemporaryDirectory() as d:
            daemon = SingleResponseDaemon(d, {
                "healthy": True,
                "battery": None,
                "control_loop": {"target_hz": 50.0, "achieved_hz": 49.5,
                                 "missed": 0},
            })
            result = health_probe.probe(daemon.path)
            daemon.finish()
        self.assertEqual([r["method"] for r in daemon.requests], ["robot.health"])
        self.assertNotIn("params", daemon.requests[0])
        self.assertEqual(result["status"], "reported_healthy_unverified")
        self.assertEqual(result["motor_commands_issued"], 0)
        self.assertEqual(result["memory_writes"], 0)
        self.assertFalse(result["physical_safety_verified"])
        self.assertFalse(result["autonomy_executed"])
        self.assertNotIn("battery", result)
        self.assertNotIn("achieved_hz", result)

    def test_unhealthy_never_promoted_to_ready(self):
        with tempfile.TemporaryDirectory() as d:
            daemon = SingleResponseDaemon(d, {"healthy": False})
            result = health_probe.probe(daemon.path)
            daemon.finish()
        self.assertEqual(result["status"], "idle_reported_unhealthy")
        self.assertEqual(len(daemon.requests), 1)

    def test_invalid_oem_response_is_idle_not_trusted(self):
        with tempfile.TemporaryDirectory() as d:
            daemon = SingleResponseDaemon(d, {"healthy": "yes"})
            result = health_probe.probe(daemon.path)
            daemon.finish()
        self.assertEqual(result["status"], "idle_no_verified_telemetry")
        self.assertEqual(len(daemon.requests), 1)

    def test_missing_socket_and_timeout_are_idle(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(
                health_probe.probe(str(Path(d) / "absent.sock"))["status"],
                "idle_no_verified_telemetry",
            )
        calls = []
        def fail(path, *, timeout_s):
            calls.append((path, timeout_s))
            raise TelemetryTimeout("fake timeout")
        result = health_probe.probe("/run/robotd.sock", reader=fail)
        self.assertEqual(result["status"], "idle_no_verified_telemetry")
        self.assertEqual(calls, [("/run/robotd.sock", 1.0)])

    def test_bad_non_boolean_reading_is_idle(self):
        class Invalid:
            healthy = "true"
        result = health_probe.probe("/run/robotd.sock",
                                    reader=lambda *_args, **_kw: Invalid())
        self.assertEqual(result["status"], "idle_invalid_health")

    def test_no_process_loop_or_motor_api_in_probe(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for forbidden in ("robot.move", "robot.do", "robot.stop", "robot.init",
                          "subprocess", "sqlite3", "requests", "qwen", "while True",
                          "robot.subscribe", "tof.stream"):
            self.assertNotIn(forbidden, text)
        self.assertEqual(text.count("read_health("), 0)  # only injected reader once
        self.assertIn("reader(socket_path, timeout_s=1.0)", text)

    def test_oem_p14a_source_closure_unchanged(self):
        source = current_source(ROOT)
        self.assertEqual(len(source), 19)
        self.assertFalse(any("health_probe" in f for f in source))
        self.assertEqual(
            sorted(f for f in source if f.endswith("/sim_ipc.py")),
            ["microduck_companion/sim_ipc.py"],
        )

    def test_service_disabled_and_source_layer_dev_only(self):
        unit = UNIT.read_text(encoding="utf-8")
        recipe = RECIPE.read_text(encoding="utf-8")
        selection = DEV_APPEND.read_text(encoding="utf-8")
        self.assertIn("Type=oneshot", unit)
        self.assertIn("After=robotd.service", unit)
        self.assertNotIn("Wants=robotd.service", unit)
        self.assertNotIn("Requires=robotd.service", unit)
        self.assertIn("DynamicUser=yes", unit)
        self.assertIn("SupplementaryGroups=robot", unit)  # developer-only risk
        self.assertIn("RestrictAddressFamilies=AF_UNIX", unit)
        self.assertIn("NoNewPrivileges=yes", unit)
        self.assertIn("ProtectSystem=strict", unit)
        active_unit_lines = [line.strip() for line in unit.splitlines()
                             if line.strip() and not line.lstrip().startswith("#")]
        self.assertNotIn("[Install]", active_unit_lines)
        self.assertNotIn("WantedBy=", unit)
        self.assertNotIn("Restart=", unit)
        self.assertNotIn("ExecStartPre=", unit)
        self.assertEqual(unit.count("ExecStart="), 1)
        self.assertIn("python3 -I -B @LIBEXECDIR@/kwipi/health_probe.py", unit)
        self.assertIn('SYSTEMD_AUTO_ENABLE:${PN} = "disable"', recipe)
        self.assertIn('RDEPENDS:${PN} += "kwipi-companion python3-core python3-json"', recipe)
        self.assertIn("inherit allarch systemd", recipe)
        self.assertIn('IMAGE_INSTALL:append = " kwipi-readonly-probe"', selection)
        self.assertFalse((LAYER / "recipes-core/images/microduck-image.bbappend").exists())

    def test_dev_image_cannot_auto_enable_without_explicit_new_code(self):
        unit = UNIT.read_text(encoding="utf-8")
        recipe = RECIPE.read_text(encoding="utf-8")
        with self.assertRaises(AssertionError):
            changed_lines = [line.strip() for line in
                             (unit + "\n[Install]\nWantedBy=multi-user.target\n").splitlines()
                             if line.strip() and not line.lstrip().startswith("#")]
            self.assertNotIn("[Install]", changed_lines)
        with self.assertRaises(AssertionError):
            self.assertIn('SYSTEMD_AUTO_ENABLE:${PN} = "disable"',
                          recipe.replace(' = "disable"', ' = "enable"'))
        self.assertNotIn("microduck-image.bbappend",
                         DEV_APPEND.name)


if __name__ == "__main__":
    unittest.main()
