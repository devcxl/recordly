from pathlib import Path
import json
import os
import re
import sys
from tempfile import TemporaryDirectory
import unittest

from cabbage_cli.scaffold import init_project, new_change, adopt_project, discard_change
from cabbage_cli.core import (
    CabbageError,
    verify_stage,
    sync_change_to_docs,
    current_signature,
    load_yaml,
    dump_yaml,
    write_text_atomic,
    is_code_change,
    load_config,
    stage_statuses,
)


def fill_template(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"<!--\s*CABBAGE:.*?-->", "Completed content.", text, flags=re.S)
    path.write_text(text, encoding="utf-8")


class CabbageEngineEnhancementsTest(unittest.TestCase):
    def test_dependency_cycle_detection(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            init_project(root)
            new_change(root, "feature", "test-cycle")

            # Introduce a cycle in feature.yaml: requirement -> design -> requirement
            wf_path = root / ".cabbage/workflows/feature.yaml"
            wf = load_yaml(wf_path)
            for stage in wf["stages"]:
                if stage["id"] == "requirement":
                    stage["depends_on"] = ["design"]
            dump_yaml(wf_path, wf)

            with self.assertRaisesRegex(CabbageError, "dependency cycle detected"):
                current_signature(root, "test-cycle", "requirement")

    def test_atomic_write_and_yaml_error(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            test_file = root / "atomic.txt"
            write_text_atomic(test_file, "atomic content")
            self.assertEqual("atomic content", test_file.read_text(encoding="utf-8"))

            yaml_file = root / "bad.yaml"
            yaml_file.write_text("key: [unclosed list", encoding="utf-8")
            with self.assertRaisesRegex(CabbageError, "invalid YAML"):
                load_yaml(yaml_file)

    def test_mermaid_validation(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            init_project(root)
            new_change(root, "feature", "test-mermaid")

            prd = root / ".cabbage/changes/test-mermaid/prd.md"
            fill_template(prd)
            base_content = prd.read_text(encoding="utf-8")

            # 1. Unclosed mermaid
            prd.write_text(base_content + "\n```mermaid\ngraph TD\n  A --> B\n", encoding="utf-8")
            with self.assertRaisesRegex(CabbageError, "unclosed Mermaid block"):
                verify_stage(root, "test-mermaid", "requirement")

            # 2. Empty mermaid
            prd.write_text(base_content + "\n```mermaid\n```\n", encoding="utf-8")
            with self.assertRaisesRegex(CabbageError, "empty Mermaid diagram block"):
                verify_stage(root, "test-mermaid", "requirement")

            # 3. Valid mermaid
            prd.write_text(base_content + "\n```mermaid\nflowchart TD\n  A --> B\n```\n", encoding="utf-8")
            verify_stage(root, "test-mermaid", "requirement")

    def test_checklist_skipped_tasks(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            init_project(root)
            new_change(root, "feature", "test-tasks")

            for stage in ("requirement", "impact", "design", "tests"):
                artifact = next(
                    item["artifact"]
                    for item in stage_statuses(root, "test-tasks")
                    if item["id"] == stage
                )
                fill_template(root / ".cabbage/changes/test-tasks" / artifact)
                verify_stage(root, "test-tasks", stage)

            tasks = root / ".cabbage/changes/test-tasks/tasks.md"
            fill_template(tasks)
            # Mix of checked and skipped tasks
            tasks_content = tasks.read_text(encoding="utf-8")
            tasks_content = tasks_content.replace("- [ ]", "- [x]", 2)
            tasks_content = tasks_content.replace("- [ ]", "- [-]")
            tasks.write_text(tasks_content, encoding="utf-8")

            # Should verify successfully since [-] is not considered unchecked
            verify_stage(root, "test-tasks", "implementation")

    def test_markdown_anchors_and_links(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            init_project(root)
            new_change(root, "feature", "test-links")

            prd = root / ".cabbage/changes/test-links/prd.md"
            fill_template(prd)
            base_content = prd.read_text(encoding="utf-8")

            # 1. Broken internal anchor
            prd.write_text(base_content + "\n[Link to nowhere](#non-existent-section)\n", encoding="utf-8")
            with self.assertRaisesRegex(CabbageError, "broken internal anchor"):
                verify_stage(root, "test-links", "requirement")

            # 2. Valid internal anchor
            prd.write_text(base_content + "\n[Link to goal](#goal)\n", encoding="utf-8")
            verify_stage(root, "test-links", "requirement")

    def test_discard_change(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            init_project(root)
            new_change(root, "feature", "temp-change")
            self.assertTrue((root / ".cabbage/changes/temp-change").exists())

            discard_change(root, "temp-change")
            self.assertFalse((root / ".cabbage/changes/temp-change").exists())

            with self.assertRaisesRegex(CabbageError, "does not exist"):
                discard_change(root, "temp-change")

    def test_adopt_apply(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            init_project(root)
            (root / "adr").mkdir()
            (root / "adr/0001-database.md").write_text("# ADR Database\n", encoding="utf-8")
            (root / "notes").mkdir()
            (root / "notes/api-guide.md").write_text("# API Guide\n", encoding="utf-8")

            res = adopt_project(root, apply=True)
            self.assertTrue((root / "docs/03-architecture/adr/0001-database.md").exists())
            self.assertTrue((root / "docs/05-api/api-guide.md").exists())
            self.assertFalse((root / "adr/0001-database.md").exists())
            self.assertFalse((root / "notes/api-guide.md").exists())

    def test_custom_docs_mapping(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            init_project(root)
            cfg = load_config(root)
            cfg.setdefault("docs", {})["mapping"] = {"requirement": "01-custom-product/{change_id}.md"}
            dump_yaml(root / ".cabbage/config.yaml", cfg)

            new_change(root, "feature", "mapped-change")
            fill_template(root / ".cabbage/changes/mapped-change/prd.md")
            verify_stage(root, "mapped-change", "requirement")

            synced = sync_change_to_docs(root, "mapped-change")
            self.assertTrue((root / "docs/01-custom-product/mapped-change.md").exists())

    def test_is_code_change(self):
        cfg = {"ci": {"exclude_prefixes": ["docs/", ".cabbage/"]}}
        # Non-code files
        self.assertFalse(is_code_change(".gitignore", cfg))
        self.assertFalse(is_code_change(".editorconfig", cfg))
        self.assertFalse(is_code_change("Makefile", cfg))
        self.assertFalse(is_code_change("README.md", cfg))
        self.assertFalse(is_code_change("docs/01-product/intro.md", cfg))
        # Code files
        self.assertTrue(is_code_change("src/main.py", cfg))
        self.assertTrue(is_code_change("cabbage_cli/core.py", cfg))
        self.assertTrue(is_code_change("README_tool.py", cfg))


    def test_ci_check_with_git(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            # Initialize git repository
            import subprocess
            subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "tester"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=root, check=True)

            init_project(root)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True)

            # Create feature branch with code change but no cabbage change
            subprocess.run(["git", "checkout", "-b", "feature-branch"], cwd=root, check=True)
            (root / "src").mkdir()
            (root / "src/app.py").write_text("print('hello')\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "add app"], cwd=root, check=True)

            from cabbage_cli.core import ci_check
            errors = ci_check(root, "main")
            self.assertTrue(any("code changed but no active .cabbage/changes" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
