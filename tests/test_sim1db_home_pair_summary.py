"""B1 workflow summary fixtures only: no OEM daemon, image or model execution."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

WORKFLOW = (Path(__file__).resolve().parents[1] / '.github/workflows'
            / 'sim-1c-oem-live-camera.yml')


def summary_source() -> str:
    """Exercise the actual workflow code instead of a copied implementation."""
    text = WORKFLOW.read_text(encoding='utf-8')
    marker = "          python3 - <<'PYSUM'\n"
    if text.count(marker) != 1:
        raise AssertionError('expected one B1 summary')
    return textwrap.dedent(text.split(marker, 1)[1].split('\n          PYSUM', 1)[0])


def series_fixture(case: str) -> dict:
    return {
        'status': 'PASS_2HZ_OEM_READONLY_MOCK_F2', 'launch_context_verified': True,
        'world_case_requested': case, 'world_contains_ball_xml': case == 'ball',
        'completed_cycles': 10, 'requested_cycles': 10, 'motor_commands_issued': 0,
        'experience_writes': 0, 'semantic_category_verified': False,
        'pixel_gt_synchronised': False, 'image_written': False,
        'launch_context': {'initial_keyframe': 'HOME'},
        'samples': [{'regions_untrusted_count': 1}] * 10,
        'f2_inspect_unknown_count': 5, 'f2_idle_count': 5,
    }


def negative_fixture(case: str) -> dict:
    return {'status': 'STOP_ACTIVE_WORLD_UNVERIFIED', 'completed_cycles': 0,
            'actual_case_checked': case, 'actual_initial_keyframe': 'HOME'}


class HomePairSummaryTests(unittest.TestCase):
    def run_fixture(self, change=None):
        with tempfile.TemporaryDirectory(prefix='sim1db-summary-fixture-') as name:
            root = Path(name)
            for case in ('ball', 'empty'):
                report, negative = series_fixture(case), negative_fixture(case)
                if change is not None and case == 'ball':
                    key, value = change
                    if key == 'initial':
                        report['launch_context']['initial_keyframe'] = value
                    elif key == 'negative_status':
                        negative['status'] = value
                    elif key == 'negative_actual':
                        negative['actual_case_checked'] = value
                    elif key == 'missing':
                        continue
                    else:
                        report[key] = value
                (root / f'sim-1d-{case}-2hz.json').write_text(json.dumps(report))
                (root / f'sim-1db-{case}-negative.json').write_text(json.dumps(negative))
            completed = subprocess.run(
                [sys.executable, '-c', summary_source()], check=False,
                capture_output=True, text=True, timeout=5,
                env=dict(os.environ, RUNNER_TEMP=str(root)),
            )
            self.assertEqual(completed.returncode, 0 if change is None else 1,
                             completed.stdout + completed.stderr)
            result = json.loads((root / 'sim-1db-home-pair.json').read_text())
            self.assertEqual(result['status'], 'PASS_MATCHED_HOME_INITIALISATION_ONLY'
                             if change is None else 'STOP_INCOMPLETE_HOME_PAIR')
            for key in ('pixel_gt_synchronised', 'actual_camera_pose_matched',
                        'ball_recognition_verified', 'memory_effect_verified',
                        'robot_validated'):
                self.assertIs(result[key], False)
            return result

    def test_same_initial_home_only_never_recognition_or_robot(self):
        result = self.run_fixture()
        self.assertEqual(len(result['rows']), 2)
        self.assertTrue(all(row['pass_initial_home_protocol'] for row in result['rows']))

    def test_thirteen_negative_cases_cannot_be_a_pass(self):
        changes = (
            ('initial', 'SIT'), ('completed_cycles', 9),
            ('launch_context_verified', False), ('world_case_requested', 'empty'),
            ('world_contains_ball_xml', False), ('motor_commands_issued', 1),
            ('experience_writes', 1), ('semantic_category_verified', True),
            ('pixel_gt_synchronised', True), ('image_written', True),
            ('negative_status', 'PASS'), ('negative_actual', 'empty'), ('missing', True),
        )
        for change in changes:
            with self.subTest(change=change):
                result = self.run_fixture(change)
                self.assertFalse(result['rows'][0]['pass_initial_home_protocol'])


if __name__ == '__main__':
    unittest.main()
