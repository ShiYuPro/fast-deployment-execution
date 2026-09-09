#!/usr/bin/env python3

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


RUNNER = Path(__file__).with_name("deploy_runner.py")


class DeployRunnerTests(unittest.TestCase):
    def make_plan(self, root: Path) -> Path:
        plan = {
            "version": 1,
            "name": "fixture",
            "deadline_seconds": 60,
            "state_file": "state.json",
            "phases": [
                {
                    "id": "preflight",
                    "kind": "preflight",
                    "argv": [sys.executable, "-c", "open('preflight', 'a').write('1')"],
                    "reusable_seconds": 60,
                },
                {
                    "id": "dry-run",
                    "kind": "dry-run",
                    "argv": [sys.executable, "-c", "open('dry-run', 'w').write('ok')"],
                    "reusable_seconds": 60,
                },
                {
                    "id": "deploy",
                    "kind": "deploy",
                    "argv": [sys.executable, "-c", "open('deployed', 'w').write('yes')"],
                },
                {
                    "id": "verify",
                    "kind": "verify",
                    "argv": [sys.executable, "-c", "assert open('deployed').read() == 'yes'"],
                },
            ],
        }
        path = root / "plan.json"
        path.write_text(json.dumps(plan), encoding="utf-8")
        return path

    def run_runner(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(RUNNER), *args], text=True, capture_output=True, check=False
        )

    def test_dry_run_stops_before_deploy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self.make_plan(root)
            result = self.run_runner("dry-run", str(plan))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((root / "dry-run").exists())
            self.assertFalse((root / "deployed").exists())
            self.assertIn("DRY_RUN_PHASES_COMPLETE", result.stdout)

    def test_deploy_requires_execute_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.make_plan(Path(directory))
            result = self.run_runner("deploy", str(plan))
            self.assertEqual(result.returncode, 2)
            self.assertIn("BLOCKED_EXECUTE_FLAG_REQUIRED", result.stderr)

    def test_deploy_reruns_preflight_despite_ttl(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self.make_plan(root)
            first = self.run_runner("dry-run", str(plan))
            self.assertEqual(first.returncode, 0, first.stderr)
            second = self.run_runner("deploy", str(plan), "--execute")
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual((root / "preflight").read_text(), "11")
            self.assertTrue((root / "deployed").exists())
            self.assertNotIn("PHASE_REUSED", second.stdout)
            self.assertIn("PHASE_START id=dry-run", second.stdout)

    def test_failure_stops_before_deploy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self.make_plan(root)
            data = json.loads(plan.read_text())
            data['phases'][0]['argv'] = [sys.executable, '-c', 'raise SystemExit(7)']
            plan.write_text(json.dumps(data))
            result = self.run_runner('deploy', str(plan), '--execute')
            self.assertEqual(result.returncode, 7)
            self.assertFalse((root / 'deployed').exists())

    def test_missing_executable_records_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self.make_plan(root)
            data = json.loads(plan.read_text())
            data['phases'][0]['argv'] = [str(root / 'does-not-exist')]
            plan.write_text(json.dumps(data))
            result = self.run_runner('deploy', str(plan), '--execute')
            self.assertEqual(result.returncode, 127)
            self.assertFalse((root / 'deployed').exists())
            self.assertEqual(json.loads((root/'state.json').read_text())['phases']['preflight']['status'], 'failed')

    def test_non_object_plan_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = Path(directory)/'plan.json'
            plan.write_text('[]')
            result = self.run_runner('check', str(plan))
            self.assertEqual(result.returncode, 2)


    def test_deploy_requires_post_deploy_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self.make_plan(root)
            data = json.loads(plan.read_text())
            data['phases'] = data['phases'][:-1]
            plan.write_text(json.dumps(data))
            result = self.run_runner('deploy', str(plan), '--execute')
            self.assertEqual(result.returncode, 2)
            self.assertIn('POST_DEPLOY_VERIFICATION_MISSING', result.stderr)
            self.assertFalse((root/'deployed').exists())


if __name__ == "__main__":
    unittest.main()
