#!/usr/bin/env python3
"""Regression tests for concrete project-package validation."""

from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path

from validate_project_package import validate_package


META = (
    "<!-- predev-meta: framework_version=0.9.0-candidate.5; package_id=REQ-001; "
    "package_version=1.0.0; baseline_status=approved; readiness=ready; development_scope=full -->"
)


@unittest.skipIf(os.name == 'nt', 'Frozen 0.9 format requires POSIX project_root; current-format Windows checks run separately')
class ProjectPackageValidatorTests(unittest.TestCase):
    def make_project(self) -> tuple[tempfile.TemporaryDirectory[str], Path, Path, dict[str, object]]:
        holder = tempfile.TemporaryDirectory()
        root = Path(holder.name) / "sample-project"
        package = root / "docs" / "pre-development" / "REQ-001-sample"
        package.mkdir(parents=True)
        manifest: dict[str, object] = {
            "framework_version": "0.9.0-candidate.5",
            "package_id": "REQ-001",
            "package_slug": "sample",
            "package_version": "1.0.0",
            "route": "complete",
            "baseline_status": "approved",
            "readiness": "ready",
            "development_scope": "full",
            "project_root": str(root.resolve()),
            "package_path": "docs/pre-development/REQ-001-sample",
            "source_policy": {
                "inheritance_mode": "deny-unless-explicit",
                "authoritative_sources": ["SRC-001"],
                "supporting_sources": [],
                "excluded_sources": ["SRC-OLD"],
            },
            "open_blockers": [],
            "open_conditions": [],
            "authorized_work": [],
            "approval": {"approved_by": ["product-owner"], "approved_at": "2026-08-12"},
            "entrypoints": {"readme": "README.md", "current_state": "docs/00-current-state.md"},
            "primary_artifact": "development-ready.md",
            "readable_artifact": "development-ready.html",
            "clarification_closures": [],
            "artifacts": ["development-ready.md", "development-ready.html", "visuals/system.svg"],
        }
        (root / "README.md").write_text(f"# Sample\n\n{META}\n", encoding="utf-8")
        (root / "docs" / "00-current-state.md").write_text(f"# Current\n\n{META}\n", encoding="utf-8")
        sections = "\n".join(f"## {number}. Section\n" for number in range(12))
        (package / "development-ready.md").write_text(
            f"# Package\n\n{META}\n\nSRC-001\nSRC-OLD is excluded.\n\n{sections}"
            "\nCOMM-001 synchronous query\n\n![System](visuals/system.svg)\n"
            "\n| Field | Value |\n| --- | --- |\n| Communication | COMM-001 |\n"
            "\n```mermaid\nflowchart LR\nA --> B\n```\n",
            encoding="utf-8",
        )
        (package / "visuals").mkdir()
        (package / "visuals" / "system.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><title>System</title><text>COMM-001</text></svg>',
            encoding="utf-8",
        )
        (package / "development-ready.html").write_text(
            f'<!doctype html><html><head>{META}</head><body><main>'
            '<table><tr><td>COMM-001</td></tr></table>'
            '<img src="visuals/system.svg" alt="System"></main></body></html>',
            encoding="utf-8",
        )
        self.write_manifest(package, manifest)
        return holder, root, package, manifest

    @staticmethod
    def write_manifest(package: Path, manifest: dict[str, object]) -> None:
        (package / "package-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def test_valid_package_passes(self) -> None:
        holder, root, package, _ = self.make_project()
        self.addCleanup(holder.cleanup)
        self.assertEqual(validate_package(root, package), [])

    def test_wrong_project_path_is_rejected(self) -> None:
        holder, root, package, manifest = self.make_project()
        self.addCleanup(holder.cleanup)
        manifest["project_root"] = str((root.parent / "lookalike-project").resolve())
        self.write_manifest(package, manifest)
        self.assertTrue(any("project_root" in error for error in validate_package(root, package)))

    def test_source_role_overlap_is_rejected(self) -> None:
        holder, root, package, manifest = self.make_project()
        self.addCleanup(holder.cleanup)
        policy = copy.deepcopy(manifest["source_policy"])
        policy["excluded_sources"] = ["SRC-001"]
        manifest["source_policy"] = policy
        self.write_manifest(package, manifest)
        self.assertTrue(any("source roles overlap" in error for error in validate_package(root, package)))

    def test_incomplete_clarification_writeback_is_rejected(self) -> None:
        holder, root, package, manifest = self.make_project()
        self.addCleanup(holder.cleanup)
        manifest["clarification_closures"] = [
            {
                "question_id": "Q-001",
                "decision_id": "USR-001",
                "impacted_ids": ["RULE-001", "CON-001", "AC-001"],
                "updated_ids": ["RULE-001", "CON-001"],
            }
        ]
        self.write_manifest(package, manifest)
        self.assertTrue(any("full impact writeback" in error for error in validate_package(root, package)))

    def test_false_ready_is_rejected(self) -> None:
        holder, root, package, manifest = self.make_project()
        self.addCleanup(holder.cleanup)
        manifest["baseline_status"] = "candidate"
        manifest["open_blockers"] = ["BLK-001"]
        self.write_manifest(package, manifest)
        errors = validate_package(root, package)
        self.assertTrue(any("candidate baseline" in error for error in errors))
        self.assertTrue(any("open blockers" in error for error in errors))

    def test_complete_route_without_communication_model_is_rejected(self) -> None:
        holder, root, package, _ = self.make_project()
        self.addCleanup(holder.cleanup)
        primary = package / "development-ready.md"
        body = primary.read_text(encoding="utf-8")
        body = body.replace("COMM-001 synchronous query\n", "")
        body = body.replace("| Communication | COMM-001 |\n", "")
        primary.write_text(body, encoding="utf-8")
        self.assertTrue(any("COMM-*" in error for error in validate_package(root, package)))

    def test_complete_route_without_visualization_is_rejected(self) -> None:
        holder, root, package, _ = self.make_project()
        self.addCleanup(holder.cleanup)
        primary = package / "development-ready.md"
        body = primary.read_text(encoding="utf-8")
        body = body.replace("```mermaid\nflowchart LR\nA --> B\n```\n", "")
        primary.write_text(body, encoding="utf-8")
        self.assertTrue(any("Mermaid" in error for error in validate_package(root, package)))

    def test_complete_route_without_readable_html_is_rejected(self) -> None:
        holder, root, package, _ = self.make_project()
        self.addCleanup(holder.cleanup)
        (package / "development-ready.html").unlink()
        self.assertTrue(any("readable" in error.lower() for error in validate_package(root, package)))

    def test_complete_route_without_visible_diagram_is_rejected(self) -> None:
        holder, root, package, _ = self.make_project()
        self.addCleanup(holder.cleanup)
        (package / "visuals" / "system.svg").unlink()
        self.assertTrue(any("artifact does not exist" in error for error in validate_package(root, package)))

    def test_standard_route_without_readable_artifact_is_rejected(self) -> None:
        holder, root, package, manifest = self.make_project()
        self.addCleanup(holder.cleanup)
        manifest["route"] = "standard"
        manifest.pop("readable_artifact")
        manifest["artifacts"] = ["development-ready.md", "visuals/system.svg"]
        self.write_manifest(package, manifest)
        self.assertTrue(any("standard-route" in error for error in validate_package(root, package)))

    def test_standard_route_with_unrendered_table_is_rejected(self) -> None:
        holder, root, package, manifest = self.make_project()
        self.addCleanup(holder.cleanup)
        manifest["route"] = "standard"
        self.write_manifest(package, manifest)
        (package / "development-ready.html").write_text(
            f"<!doctype html><html><head>{META}</head><body><main>No table</main></body></html>",
            encoding="utf-8",
        )
        self.assertTrue(any("did not render all Markdown tables" in error for error in validate_package(root, package)))


if __name__ == "__main__":
    unittest.main()
