"""Linux launch evidence fixtures, not an OEM simulation or pixel GT."""
from pathlib import Path
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from experiments import sim1d_launch_context as guard


ROOT = Path(guard.__file__).resolve().parents[1]
STATE = Path('/tmp/kwipi-sim1d-context-test')
RL = ROOT / 'upstream/microduck_rl'
OEM = ROOT / 'upstream/microduck'


def arguments(case='ball', keyframe='HOME'):
    body = [str(RL / '.venv/bin/python'), '-m', guard.MODULE,
            '--port', '17841', '--ducks', '1', '--keyframe', keyframe,
            '--headless', '--cameras', 'a', '--frame-port', '17941',
            '--camera-fps', '30']
    if case == 'ball':
        body += ['--scene', str(RL / 'src/mjlab_microduck/robot/microduck/scene_ball.xml')]
    robot = [str(OEM / 'target/debug/robotd'), '--sim', '127.0.0.1:17841',
             '--params', str(STATE / 'robotd-duck-a.toml'),
             '--socket', str(STATE / 'duck-a.sock')]
    media = [str(OEM / 'target/debug/mediad'),
             '--sim-camera', '127.0.0.1:17941',
             '--config', str(STATE / 'mediad-duck-a.toml'),
             '--robot-socket', str(STATE / 'duck-a.sock'),
             '--tof-socket', str(STATE / 'duck-a-tof.sock'),
             '--config-socket', str(STATE / 'duck-a-config.sock'),
             '--updater-socket', str(STATE / 'duck-a-updater.sock'),
             '--token', str(STATE / 'duck-a/hf-token'),
             '--frame-socket', str(STATE / 'duck-a-frame.sock'),
             '--port', '8443', '--web-port', '8080']
    return tuple(body), tuple(robot), tuple(media)


def validate(args, case='ball'):
    return guard.validate_launch_args(*args, state_dir=STATE, rl_dir=RL,
                                     oem_dir=OEM, world_case=case)


class LaunchArgumentsTests(unittest.TestCase):
    def test_three_supported_world_and_initial_pose_pairs(self):
        for case, pose in [('ball', 'HOME'), ('empty', 'HOME'), ('empty', 'SIT')]:
            with self.subTest(case=case, pose=pose):
                result = validate(arguments(case, pose), case)
                self.assertEqual(result['scene'], guard.SCENES[case])
                self.assertEqual(result['initial_keyframe'], pose)

    def test_inverted_world_label_rejected_both_ways(self):
        for active, requested in [('ball', 'empty'), ('empty', 'ball')]:
            with self.subTest(active=active):
                with self.assertRaises(guard.LaunchContextError):
                    validate(arguments(active), requested)

    def test_duplicate_or_ambiguous_options_rejected(self):
        for suffix in [('--scene', '/tmp/other.xml'), ('--port', '17841'),
                       ('--headless',), ('--port=17841',), ('--scene',)]:
            body, robot, media = arguments()
            with self.subTest(suffix=suffix):
                with self.assertRaises(guard.LaunchContextError):
                    validate((body + suffix, robot, media))

    def test_wrong_process_or_cross_wired_socket_rejected(self):
        for part, old, new in [
            (0, guard.MODULE, 'another.module'),
            (1, '127.0.0.1:17841', '127.0.0.1:17842'),
            (2, '127.0.0.1:17941', '127.0.0.1:17942'),
            (2, str(STATE / 'duck-a-frame.sock'), '/tmp/another.sock'),
            (1, str(OEM / 'target/debug/robotd'), '/tmp/robotd'),
        ]:
            args = list(arguments())
            args[part] = tuple(new if word == old else word for word in args[part])
            with self.subTest(part=part, old=old):
                with self.assertRaises(guard.LaunchContextError):
                    validate(tuple(args))

    def test_invalid_body_configuration_rejected(self):
        for old, new in [('HOME', 'SIT'), ('17841', '22'), ('17941', '17841'),
                         ('30', '15'), ('a', 'all')]:
            body, robot, media = arguments()
            with self.subTest(old=old):
                with self.assertRaises(guard.LaunchContextError):
                    validate((tuple(new if w == old else w for w in body), robot, media))

    def test_unrecognised_case_and_empty_body_rejected(self):
        for args, case in [(arguments(), 'unknown'), (((), (), ()), 'empty')]:
            with self.subTest(case=case):
                with self.assertRaises(guard.LaunchContextError):
                    validate(args, case)


class CompleteGateFixtures(unittest.TestCase):
    def run_gate(self, case='ball', *, peer_error=False, proc_error=False,
                 xml=b'<include file="ball.xml" />', pin_error=False):
        args = arguments(case)
        processes = [(100 + i, '1234', argv) for i, argv in enumerate(args)]
        with patch.object(guard, '_pin', side_effect=OSError() if pin_error else None), \
             patch.object(guard, '_process', side_effect=OSError() if proc_error else processes), \
             patch.object(guard, '_peer', side_effect=OSError() if peer_error else None,
                          return_value=(1, 2)), \
             patch.object(guard, '_listeners'), patch.object(guard, '_read', return_value=xml):
            return guard.verify_launch_context(STATE, case)

    def test_checked_launch_still_grants_no_pixel_or_robot_authority(self):
        result = self.run_gate()
        self.assertTrue(result['launch_scene_contains_ball_xml'])
        for key in ('actual_camera_pose_verified', 'same_mujoco_step_verified',
                    'sensor_source_authenticated'):
            self.assertIs(result[key], False)
        self.assertNotIn('frame_ball_visibility_known', result)

    def test_empty_launch_is_checked_from_xml_not_just_argument(self):
        result = self.run_gate('empty', xml=b'<mujoco />')
        self.assertFalse(result['launch_scene_contains_ball_xml'])
        with self.assertRaises(guard.LaunchContextError):
            self.run_gate('empty')

    def test_missing_or_recycled_pid_wrong_peer_and_pin_fail_closed(self):
        for kwargs in [{'peer_error': True}, {'proc_error': True}, {'pin_error': True}]:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(guard.LaunchContextError):
                    self.run_gate(**kwargs)


@unittest.skipUnless(sys.platform == 'linux', 'Linux process/socket fixtures only')
class RealLinuxPrimitiveTests(unittest.TestCase):
    def test_local_socket_peer_pid_and_regular_file_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'peer.sock'
            with socket.socket(socket.AF_UNIX) as server:
                server.bind(str(path))
                server.listen(4)
                self.assertEqual(guard._peer(path, os.getpid()),
                                 (path.stat().st_dev, path.stat().st_ino))
                with self.assertRaises(guard.LaunchContextError):
                    guard._peer(path, os.getpid() + 100000)
            regular = Path(directory) / 'not-a-socket'
            regular.write_text('fixture')
            with self.assertRaises(guard.LaunchContextError):
                guard._peer(regular, os.getpid())

    def test_live_process_and_stale_or_symlink_pidfile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
            try:
                (root / 'body.pid').write_text(str(child.pid))
                pid, ticks, argv = guard._process(root, 'body')
                self.assertEqual(pid, child.pid)
                self.assertTrue(ticks.isdigit())
                self.assertEqual(argv[0], sys.executable)
                (root / 'alias.pid').symlink_to(root / 'body.pid')
                with self.assertRaises(guard.LaunchContextError):
                    guard._process(root, 'alias')
            finally:
                child.terminate()
                child.wait(timeout=5)
            with self.assertRaises(OSError):
                guard._process(root, 'body')

    def test_listener_must_belong_to_the_body_pid(self):
        with socket.socket() as first, socket.socket() as second:
            first.bind(('127.0.0.1', 0))
            second.bind(('127.0.0.1', 0))
            first.listen(1)
            second.listen(1)
            ports = (first.getsockname()[1], second.getsockname()[1])
            guard._listeners(os.getpid(), ports)
            second.close()
            with self.assertRaises(guard.LaunchContextError):
                guard._listeners(os.getpid(), ports)


if __name__ == '__main__':
    unittest.main()
