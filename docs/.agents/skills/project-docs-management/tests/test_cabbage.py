from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest

from cabbage_cli.scaffold import init_project, new_change
from cabbage_cli.core import (
    CabbageError,
    verify_stage,
    sync_change_to_docs,
    gate,
    stage_statuses,
    validate_change,
)


def fill_template(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"<!--\s*CABBAGE:.*?-->", "Completed content.", text, flags=re.S)
    path.write_text(text, encoding="utf-8")


class CabbageWorkflowTest(unittest.TestCase):
    def test_unedited_template_cannot_be_verified(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            init_project(root)
            new_change(root, "feature", "add-login")

            self.assertEqual([], validate_change(root, "add-login"))
            with self.assertRaisesRegex(CabbageError, "placeholder content remains"):
                verify_stage(root, "add-login", "requirement")

    def test_legacy_unedited_template_cannot_be_verified(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            init_project(root)
            new_change(root, "feature", "add-login")
            prd = root / ".cabbage/changes/add-login/prd.md"
            prd.write_text(
                """---
change: add-login
cabbage_stage: requirement
change_type: feature
---

# Goal

Replace this text with the product goal.

# Scope

Describe in-scope and out-of-scope behavior.

# Acceptance Criteria

- Define observable acceptance criteria.
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(CabbageError, "placeholder content remains"):
                verify_stage(root, "add-login", "requirement")

    def test_verification_validation_rejects_unedited_templates(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            init_project(root)
            new_change(root, "feature", "add-login")

            errors = validate_change(root, "add-login", verification=True)

            self.assertTrue(
                any("placeholder content remains" in error for error in errors)
            )

    def test_gate_and_stale_propagation(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            init_project(root)
            new_change(root, "feature", "add-login")

            self.assertTrue(gate(root, "add-login", "implementation"))
            for stage in ("requirement", "impact", "design", "tests"):
                artifact = next(
                    item["artifact"]
                    for item in stage_statuses(root, "add-login")
                    if item["id"] == stage
                )
                fill_template(root / ".cabbage/changes/add-login" / artifact)
                verify_stage(root, "add-login", stage)

            tasks = root / ".cabbage/changes/add-login/tasks.md"
            fill_template(tasks)
            tasks.write_text(tasks.read_text().replace("- [ ]", "- [x]"))
            verify_stage(root, "add-login", "implementation")
            self.assertEqual([], gate(root, "add-login", "merge"))

            # Sync spec to docs
            synced = sync_change_to_docs(root, "add-login")
            self.assertTrue(len(synced) > 0)
            self.assertTrue((root / "docs/01-product/add-login.md").exists())

            prd = root / ".cabbage/changes/add-login/prd.md"
            prd.write_text(prd.read_text() + "\nChanged requirement.\n")
            statuses = {x["id"]: x["status"] for x in stage_statuses(root, "add-login")}
            self.assertEqual("stale", statuses["requirement"])
            self.assertEqual("stale", statuses["design"])
            self.assertEqual("stale", statuses["implementation"])

    def test_verify_and_archive_syncs_docs(self):
        import subprocess, sys, os
        repository = Path(__file__).parents[1]
        with TemporaryDirectory() as td:
            root = Path(td)
            init_project(root)
            new_change(root, "feature", "new-checkout")

            for stage in ("requirement", "impact", "design", "tests"):
                artifact = next(
                    item["artifact"]
                    for item in stage_statuses(root, "new-checkout")
                    if item["id"] == stage
                )
                fill_template(root / ".cabbage/changes/new-checkout" / artifact)
                verify_stage(root, "new-checkout", stage)

            tasks = root / ".cabbage/changes/new-checkout/tasks.md"
            fill_template(tasks)
            tasks.write_text(tasks.read_text().replace("- [ ]", "- [x]"))
            verify_stage(root, "new-checkout", "implementation")

            # Run archive via CLI
            res = subprocess.run(
                [sys.executable, "-m", "cabbage_cli", "archive", "new-checkout"],
                cwd=root,
                env={**os.environ, "PYTHONPATH": str(repository)},
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, res.returncode, res.stderr)
            self.assertIn("synced", res.stdout)
            self.assertIn("archived to", res.stdout)
            self.assertTrue((root / "docs/01-product/new-checkout.md").exists())
            self.assertFalse((root / ".cabbage/changes/new-checkout").exists())


if __name__ == "__main__":
    unittest.main()
