"""N2: imported mock fixtures stay optional; no real sensor or motor is used."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class N2LazyBoundaryTests(unittest.TestCase):
    def test_f2_passive_and_personality_do_not_load_mock_engines(self):
        script = '''
import sys
from microduck_companion import AutonomyBrain, ExperienceMemory, PassiveObservationJournal, PassiveIntent
from microduck_companion.passive_sources import PassiveRead
from microduck_companion.perception import PerceptionSnapshot
m = ExperienceMemory(':memory:')
j = PassiveObservationJournal(m)
b = AutonomyBrain(m)
reading = PassiveRead('unavailable_or_invalid', PerceptionSnapshot('mock', (), 1.0))
intent = b.propose_balanced_passive(reading, journal=j, now_monotonic_s=1.0, now_wall_epoch_s=100.0)
assert (intent.intention, intent.executed, intent.motor_commands_issued) == ('idle', False, 0)
portrait = b.describe_behavior(PassiveIntent('idle', 'no_current_observation'), journal=j, now_wall_epoch_s=100.0)
assert portrait.state == 'Chill' and portrait.motor_commands_issued == 0
assert not any(k.startswith('microduck_companion.mock_') for k in sys.modules), 'unexpected mock runner/social import'
assert not any(k.startswith('microduck_companion.sim_') for k in sys.modules), 'unexpected simulator import'
m.close()
'''
        # -I removes the default cwd; absolute source root is inserted explicitly.
        complete = subprocess.run(
            [sys.executable, '-I', '-B', '-c',
             'import sys; sys.path.insert(0, sys.argv[1])\n' + script,
             str(ROOT)], check=False, capture_output=True, text=True, timeout=10,
            cwd=ROOT,
        )
        self.assertEqual(complete.returncode, 0, complete.stdout + complete.stderr)

    def test_existing_mock_record_requires_genuine_runner(self):
        from microduck_companion.episodic_memory import ExperienceMemory
        from microduck_companion.behavioral_memory import BehavioralMemory
        from microduck_companion.mock_cycles import MockCycleRunner
        memory = ExperienceMemory(':memory:')
        try:
            record = BehavioralMemory(memory)
            with self.assertRaisesRegex(TypeError, 'existing P2a mock runner'):
                record.record(runner=object(), sequence=1, now_wall_epoch_s=100.0)
            runner = MockCycleRunner(memory, session='n2-lazy')
            self.assertFalse(record.record(runner=runner, sequence=1, now_wall_epoch_s=100.0))
            self.assertEqual(record.summary(now_wall_epoch_s=100.0).executed_actions, 0)
        finally:
            memory.close()

    def test_social_proposal_still_describes_without_becoming_an_action(self):
        from microduck_companion import AutonomyBrain, ExperienceMemory, PassiveObservationJournal
        from microduck_companion.mock_social_cues import MockSocialPlan
        memory = ExperienceMemory(':memory:')
        try:
            brain = AutonomyBrain(memory)
            journal = PassiveObservationJournal(memory)
            plan = MockSocialPlan('silence', 'mock_scenario')
            portrait = brain.describe_behavior(plan, journal=journal, now_wall_epoch_s=100.0)
            self.assertEqual((portrait.state, portrait.reason), ('Chill', 'mock_social_silence'))
            self.assertEqual((portrait.executed, portrait.motor_commands_issued), (False, 0))
            with self.assertRaises(ValueError):
                MockSocialPlan('silence', 'mock_scenario', executed=True)
            with self.assertRaises(TypeError):
                brain.describe_behavior(object(), journal=journal, now_wall_epoch_s=100.0)
        finally:
            memory.close()

    def test_brain_and_journal_must_use_same_sqlite(self):
        from microduck_companion import AutonomyBrain, ExperienceMemory, PassiveObservationJournal
        from microduck_companion.passive_sources import PassiveRead
        from microduck_companion.perception import PerceptionSnapshot
        first, other = ExperienceMemory(':memory:'), ExperienceMemory(':memory:')
        try:
            brain = AutonomyBrain(first)
            journal = PassiveObservationJournal(other)
            with self.assertRaisesRegex(ValueError, 'share SQLite'):
                brain.propose_balanced_passive(
                    PassiveRead('unavailable_or_invalid', PerceptionSnapshot('mock', (), 1.0)),
                    journal=journal, now_monotonic_s=1.0, now_wall_epoch_s=100.0)
        finally:
            first.close()
            other.close()


if __name__ == '__main__':
    unittest.main()
