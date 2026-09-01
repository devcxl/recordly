import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import tomllib
import unittest


class CabbageRenameTest(unittest.TestCase):
    def test_cabbage_package_is_available(self):
        self.assertIsNotNone(importlib.util.find_spec("cabbage_cli"))

    def test_cabbage_module_exposes_cabbage_cli(self):
        result = subprocess.run(
            [sys.executable, "-m", "cabbage_cli", "--help"],
            cwd=Path(__file__).parents[1],
            text=True,
            capture_output=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("usage: cabbage", result.stdout)

    def test_cabbage_init_uses_cabbage_paths(self):
        repository = Path(__file__).parents[1]
        with TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-m", "cabbage_cli", "init", "--no-vendor-cli"],
                cwd=directory,
                env={**os.environ, "PYTHONPATH": str(repository)},
                text=True,
                capture_output=True,
            )
            root = Path(directory)

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((root / ".cabbage/config.yaml").is_file())
            self.assertTrue((root / ".github/workflows/cabbage.yml").is_file())
            config = (root / ".cabbage/config.yaml").read_text(encoding="utf-8")
            self.assertRegex(config, r"(?m)^    testing:\n    - docs/08-testing/$")

    def test_cabbage_init_uses_buildable_docs_dependencies(self):
        repository = Path(__file__).parents[1]
        with TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-m", "cabbage_cli", "init"],
                cwd=directory,
                env={**os.environ, "PYTHONPATH": str(repository)},
                text=True,
                capture_output=True,
            )
            root = Path(directory)
            generated = json.loads(
                (root / "docs/package.json").read_text(encoding="utf-8")
            )
            vendored = json.loads(
                (
                    root
                    / ".cabbage/tooling/cabbage_cli/assets/docs-site/package.json"
                ).read_text(encoding="utf-8")
            )
            config = (root / "docs/.vitepress/config.ts").read_text(encoding="utf-8")

            self.assertEqual(0, result.returncode, result.stderr)
            for package in (generated, vendored):
                dependencies = package["devDependencies"]
                self.assertEqual(
                    "^1.6.4", dependencies["vitepress"]
                )
                self.assertEqual("^2.0.17", dependencies["vitepress-plugin-mermaid"])
                self.assertEqual("^11.4.1", dependencies["mermaid"])
            self.assertIn("withMermaid", config)

    def test_project_metadata_exposes_only_cabbage(self):
        repository = Path(__file__).parents[1]
        metadata = tomllib.loads(
            (repository / "pyproject.toml").read_text(encoding="utf-8")
        )

        self.assertEqual(
            {"cabbage": "cabbage_cli.cli:main"}, metadata["project"]["scripts"]
        )
        self.assertEqual(
            ["cabbage_cli*"], metadata["tool"]["setuptools"]["packages"]["find"]["include"]
        )
        package_data = metadata["tool"]["setuptools"]["package-data"]["cabbage_cli"]
        self.assertIn("assets/docs-site/.vitepress/*", package_data)

    def test_vendored_cabbage_cli_can_run(self):
        repository = Path(__file__).parents[1]
        with TemporaryDirectory() as directory:
            init_result = subprocess.run(
                [sys.executable, "-m", "cabbage_cli", "init"],
                cwd=directory,
                env={**os.environ, "PYTHONPATH": str(repository)},
                text=True,
                capture_output=True,
            )
            vendored_path = Path(directory) / ".cabbage/tooling"
            version_result = subprocess.run(
                [sys.executable, "-m", "cabbage_cli", "--version"],
                cwd=directory,
                env={**os.environ, "PYTHONPATH": str(vendored_path)},
                text=True,
                capture_output=True,
            )

            self.assertEqual(0, init_result.returncode, init_result.stderr)
            self.assertEqual(0, version_result.returncode, version_result.stderr)
            self.assertEqual("0.1.0", version_result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
