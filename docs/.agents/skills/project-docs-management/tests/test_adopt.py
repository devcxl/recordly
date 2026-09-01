from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cabbage_cli.core import CabbageError, project_root
from cabbage_cli.scaffold import adopt_project, init_project


class CabbageAdoptTest(unittest.TestCase):
    def prepare(self, root: Path) -> None:
        init_project(root)

    def test_adopt_requires_initialized_project(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaisesRegex(CabbageError, "not a cabbage project"):
                adopt_project(root)

    def test_adopt_does_not_move_files(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            self.prepare(root)
            (root / "notes").mkdir()
            (root / "notes" / "api-guide.md").write_text("# API\n", encoding="utf-8")
            before = sorted(
                str(p.relative_to(root))
                for p in root.rglob("*.md")
                if ".cabbage/adoption-report.md" not in p.as_posix()
            )

            adopt_project(root)

            after = sorted(
                str(p.relative_to(root))
                for p in root.rglob("*.md")
                if ".cabbage/adoption-report.md" not in p.as_posix()
            )
            self.assertEqual(before, after)

    def test_adopt_writes_report_and_classifies(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            self.prepare(root)
            (root / "adr").mkdir()
            (root / "adr" / "0001-use-postgres.md").write_text("# ADR\n", encoding="utf-8")
            (root / "runbooks").mkdir()
            (root / "runbooks" / "oncall.md").write_text("# Runbook\n", encoding="utf-8")
            (root / "scratch-note.md").write_text("# ?\n", encoding="utf-8")

            data = adopt_project(root)

            rows = {r["path"]: r for r in data["documents"]}
            self.assertEqual("import", rows["adr/0001-use-postgres.md"]["action"])
            self.assertEqual("docs/03-architecture/adr", rows["adr/0001-use-postgres.md"]["target"])
            self.assertEqual("migrate", rows["runbooks/oncall.md"]["action"])
            self.assertEqual("docs/13-operations", rows["runbooks/oncall.md"]["target"])
            self.assertEqual("review", rows["scratch-note.md"]["action"])
            self.assertEqual(1, data["counts"]["import"])
            self.assertEqual(1, data["counts"]["migrate"])
            self.assertEqual(1, data["counts"]["review"])

            report = (root / ".cabbage" / "adoption-report.md").read_text(encoding="utf-8")
            self.assertIn("no files were moved", report)
            self.assertIn("`adr/0001-use-postgres.md`", report)

    def test_adopt_ignores_hidden_and_vendor_directories(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            self.prepare(root)
            for rel in ["node_modules/x/dep.md", ".venv/lib/env.md", "src/generated/build/out.md"]:
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("# x\n", encoding="utf-8")

            data = adopt_project(root)

            paths = [r["path"] for r in data["documents"]]
            self.assertNotIn("node_modules/x/dep.md", paths)
            self.assertNotIn(".venv/lib/env.md", paths)
            self.assertNotIn("src/generated/build/out.md", paths)

    def test_adopt_recognizes_conforming_docs_tree(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            self.prepare(root)
            p = root / "docs" / "05-api" / "rest-api.md"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("# API\n", encoding="utf-8")

            data = adopt_project(root)

            rows = {r["path"]: r for r in data["documents"]}
            self.assertEqual("keep", rows["docs/05-api/rest-api.md"]["action"])
            self.assertEqual("api", rows["docs/05-api/rest-api.md"]["category"])

    def test_adopt_is_idempotent(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            self.prepare(root)
            (root / "prd").mkdir()
            (root / "prd" / "checkout.md").write_text("# PRD\n", encoding="utf-8")

            first = adopt_project(root)
            second = adopt_project(root)

            self.assertEqual(first["documents"], second["documents"])


if __name__ == "__main__":
    unittest.main()
