"""Static Windows launcher contract checks; runtime still requires real Windows."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent

class LauncherContractTests(unittest.TestCase):
    def test_v2_launcher_explicitly_selects_role_and_preserves_consent(self):
        cmd = (ROOT / "SIMULER_CONSEILLER_KWIPI_V2.cmd").read_text(encoding="utf-8")
        ps = (ROOT / "scripts" / "kwipi-vision-test.ps1").read_text(encoding="utf-8")
        self.assertIn('"%~dp0scripts\\kwipi-vision-test.ps1" -RolePreview -RoleV2', cmd)
        self.assertIn('[switch]$RoleV2', ps)
        self.assertIn('if ($RoleV2 -and -not $RolePreview)', ps)
        self.assertIn('"OUI"', ps)
        self.assertIn('--role $roleName', ps)
        self.assertIn('Stop-OnlyStartedOllama', ps)
        self.assertIn('127.0.0.1', ps)
        self.assertNotIn('setx ', ps)

if __name__ == '__main__':
    unittest.main()