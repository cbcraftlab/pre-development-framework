#!/usr/bin/env python3
"""Validate a concrete pre-development package inside its target project.

The validator proves path containment, manifest shape, source-role separation,
baseline/readiness coherence, clarification closure bookkeeping, and agreement
between the manifest and the three project entry surfaces. It cannot prove that
business judgments are correct; that still requires product review and isolated
context rereading.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath

from validate_repository import validate_schema_subset


FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_SCHEMA = FRAMEWORK_ROOT / "schemas" / "legacy" / "package-manifest-0.9.schema.json"
META_PATTERN = re.compile(r"<!--\s*predev-meta:\s*([^>]+?)\s*-->")
META_KEYS = [
    "framework_version",
    "package_id",
    "package_version",
    "baseline_status",
    "readiness",
    "development_scope",
]


def within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def resolve_package_dir(project_root: Path, raw_package_dir: str) -> tuple[Path, list[str]]:
    errors: list[str] = []
    raw = Path(raw_package_dir)
    if raw.is_absolute():
        package_dir = raw.resolve()
    else:
        parsed = PurePosixPath(raw_package_dir)
        if ".." in parsed.parts:
            errors.append("package directory must not contain '..'")
        package_dir = (project_root / raw).resolve()
    if not within(package_dir, project_root):
        errors.append("package directory escapes the confirmed project root")
    return package_dir, errors


def preflight(project_root_raw: str, package_dir_raw: str) -> tuple[Path, Path, list[str]]:
    errors: list[str] = []
    raw_root = Path(project_root_raw)
    if not raw_root.is_absolute():
        errors.append("project root must be an absolute path")
    project_root = raw_root.resolve()
    if not project_root.is_dir():
        errors.append(f"project root does not exist or is not a directory: {project_root}")
    package_dir, package_errors = resolve_package_dir(project_root, package_dir_raw)
    errors.extend(package_errors)
    if package_dir == project_root:
        errors.append("package directory must be below, not equal to, the project root")
    return project_root, package_dir, errors


def parse_meta(path: Path, errors: list[str]) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"cannot read entrypoint {path}: {exc}")
        return {}
    match = META_PATTERN.search(text)
    if not match:
        errors.append(f"missing predev-meta marker: {path}")
        return {}
    result: dict[str, str] = {}
    for item in match.group(1).split(";"):
        item = item.strip()
        if not item or "=" not in item:
            continue
        key, value = item.split("=", 1)
        result[key.strip()] = value.strip()
    for key in META_KEYS:
        if key not in result:
            errors.append(f"predev-meta in {path} is missing {key}")
    return result


def check_meta(path: Path, manifest: dict[str, object], errors: list[str]) -> None:
    meta = parse_meta(path, errors)
    for key in META_KEYS:
        if key in meta and meta[key] != str(manifest.get(key, "")):
            errors.append(
                f"metadata mismatch in {path}: {key}={meta[key]!r}, "
                f"manifest={manifest.get(key)!r}"
            )


def check_source_policy(manifest: dict[str, object], errors: list[str]) -> None:
    policy = manifest["source_policy"]
    assert isinstance(policy, dict)
    roles = {
        "authoritative": set(policy["authoritative_sources"]),
        "supporting": set(policy["supporting_sources"]),
        "excluded": set(policy["excluded_sources"]),
    }
    pairs = [("authoritative", "supporting"), ("authoritative", "excluded"), ("supporting", "excluded")]
    for left, right in pairs:
        overlap = sorted(roles[left] & roles[right])
        if overlap:
            errors.append(f"source roles overlap between {left} and {right}: {overlap}")


def check_state_coherence(manifest: dict[str, object], errors: list[str]) -> None:
    baseline = manifest["baseline_status"]
    readiness = manifest["readiness"]
    scope = manifest["development_scope"]
    blockers = manifest["open_blockers"]
    conditions = manifest["open_conditions"]
    authorized = manifest["authorized_work"]
    approval = manifest["approval"]
    assert isinstance(blockers, list)
    assert isinstance(conditions, list)
    assert isinstance(authorized, list)
    assert isinstance(approval, dict)

    approved = bool(approval["approved_by"]) and bool(approval["approved_at"])
    if baseline == "candidate" and readiness in {"ready", "conditionally_ready"}:
        errors.append("candidate baseline cannot claim ready or conditionally_ready")
    if baseline == "superseded" and scope != "none":
        errors.append("superseded baseline must have development_scope=none")

    if readiness == "ready":
        if baseline != "approved" or not approved:
            errors.append("ready requires an approved baseline and approval record")
        if scope != "full":
            errors.append("ready requires development_scope=full")
        if blockers or conditions:
            errors.append("ready cannot contain open blockers or conditions")
    elif readiness == "conditionally_ready":
        if baseline != "approved" or not approved:
            errors.append("conditionally_ready requires an approved baseline and approval record")
        if scope != "bounded":
            errors.append("conditionally_ready requires development_scope=bounded")
        if blockers:
            errors.append("conditionally_ready cannot contain open blockers")
        if not conditions or not authorized:
            errors.append("conditionally_ready requires conditions and explicit authorized_work")
    else:
        if scope != "none":
            errors.append(f"{readiness} requires development_scope=none")
        if authorized:
            errors.append(f"{readiness} cannot authorize development work")


def check_clarification_closures(manifest: dict[str, object], errors: list[str]) -> None:
    for closure in manifest["clarification_closures"]:
        impacted = set(closure["impacted_ids"])
        updated = set(closure["updated_ids"])
        missing = sorted(impacted - updated)
        if missing:
            errors.append(
                f"clarification {closure['question_id']} lacks full impact writeback: {missing}"
            )


def check_artifacts(project_root: Path, package_dir: Path, manifest: dict[str, object], errors: list[str]) -> None:
    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, list)
    primary = manifest["primary_artifact"]
    if primary not in artifacts:
        errors.append("primary_artifact must be listed in artifacts")
    readable = manifest.get("readable_artifact", "")
    if readable and readable not in artifacts:
        errors.append("readable_artifact must be listed in artifacts")
    if manifest["route"] in {"standard", "complete"} and not readable:
        errors.append(f"{manifest['route']}-route package requires readable_artifact")

    for raw_path in artifacts:
        parsed = PurePosixPath(raw_path)
        if parsed.is_absolute() or ".." in parsed.parts or "\\" in raw_path:
            errors.append(f"unsafe artifact path: {raw_path}")
            continue
        path = (package_dir / raw_path).resolve()
        if not within(path, package_dir):
            errors.append(f"artifact escapes package: {raw_path}")
        elif not path.is_file():
            errors.append(f"artifact does not exist: {raw_path}")

    primary_path = (package_dir / str(primary)).resolve()
    body = ""
    image_targets: list[str] = []
    if primary_path.is_file():
        check_meta(primary_path, manifest, errors)
        body = primary_path.read_text(encoding="utf-8")
        for source_id in manifest["source_policy"]["authoritative_sources"]:
            if source_id not in body:
                errors.append(f"authoritative source missing from primary artifact: {source_id}")
        for item_id in manifest["open_blockers"] + manifest["open_conditions"]:
            if item_id not in body:
                errors.append(f"open item missing from primary artifact: {item_id}")
        if manifest["route"] == "complete":
            for section in range(12):
                if re.search(rf"^##\s+{section}\.", body, re.MULTILINE) is None:
                    errors.append(f"complete-route primary artifact missing section {section}")
            if re.search(r"\bCOMM-[A-Z0-9-]+\b", body) is None:
                errors.append("complete-route primary artifact missing COMM-* communication model")
            if "```mermaid" not in body:
                errors.append("complete-route primary artifact missing Mermaid system/interaction visualization")

            image_targets = re.findall(r"!\[[^\]]*\]\(([^\s)]+)(?:\s+\"[^\"]*\")?\)", body)
            if not image_targets:
                errors.append("complete-route primary artifact missing visible local diagram reference")
            for image_target in image_targets:
                parsed = PurePosixPath(image_target)
                if parsed.is_absolute() or ".." in parsed.parts or "\\" in image_target:
                    errors.append(f"unsafe Markdown image path: {image_target}")
                    continue
                image_path = (package_dir / image_target).resolve()
                if not within(image_path, package_dir):
                    errors.append(f"Markdown image escapes package: {image_target}")
                elif not image_path.is_file():
                    errors.append(f"Markdown image does not exist: {image_target}")
                if image_target not in artifacts:
                    errors.append(f"Markdown image missing from manifest artifacts: {image_target}")

            for image_target in image_targets:
                if not image_target.lower().endswith(".svg"):
                    continue
                image_path = (package_dir / image_target).resolve()
                if not image_path.is_file():
                    continue
                svg_body = image_path.read_text(encoding="utf-8")
                if "<svg" not in svg_body or "<title" not in svg_body:
                    errors.append(f"visible diagram is not an accessible SVG: {image_target}")

    if readable:
        readable_path = (package_dir / str(readable)).resolve()
        if not readable_path.is_file():
            errors.append(f"readable artifact does not exist: {readable}")
        else:
            check_meta(readable_path, manifest, errors)
            readable_body = readable_path.read_text(encoding="utf-8")
            if "<html" not in readable_body or "<main" not in readable_body:
                errors.append("readable artifact is not a standalone HTML document")
            if body:
                markdown_table_count = len(
                    re.findall(r"^\|.*\|\s*\n\|\s*:?-{3,}", body, re.MULTILINE)
                )
                html_table_count = len(re.findall(r"<table(?:\s|>)", readable_body))
                if markdown_table_count and html_table_count < markdown_table_count:
                    errors.append(
                        "readable artifact did not render all Markdown tables: "
                        f"markdown={markdown_table_count}, html={html_table_count}"
                    )
                html_image_sources = re.findall(r'<img[^>]+src="([^"]+)"', readable_body)
                for image_target in image_targets:
                    if image_target not in html_image_sources:
                        errors.append(f"readable artifact missing diagram image: {image_target}")


def validate_package(project_root_raw: str | Path, package_dir_raw: str | Path) -> list[str]:
    project_root, package_dir, errors = preflight(str(project_root_raw), str(package_dir_raw))
    if errors:
        return errors
    if not package_dir.is_dir():
        return [f"package directory does not exist: {package_dir}"]

    manifest_path = package_dir / "package-manifest.json"
    if not manifest_path.is_file():
        return [f"missing package manifest: {manifest_path}"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read package manifest: {exc}"]

    schema = json.loads(MANIFEST_SCHEMA.read_text(encoding="utf-8"))
    validate_schema_subset(manifest, schema, str(manifest_path), errors)
    if errors:
        return errors

    actual_relative = package_dir.relative_to(project_root).as_posix()
    expected_directory = f"{manifest['package_id']}-{manifest['package_slug']}"
    if package_dir.name != expected_directory:
        errors.append(
            f"package directory name mismatch: actual={package_dir.name}, expected={expected_directory}"
        )
    if Path(manifest["project_root"]).resolve() != project_root:
        errors.append("manifest project_root does not equal the validated project root")
    if PurePosixPath(manifest["package_path"]).as_posix() != actual_relative:
        errors.append(
            f"manifest package_path mismatch: actual={actual_relative}, "
            f"manifest={manifest['package_path']}"
        )

    check_source_policy(manifest, errors)
    check_state_coherence(manifest, errors)
    check_clarification_closures(manifest, errors)
    check_artifacts(project_root, package_dir, manifest, errors)

    entrypoints = manifest["entrypoints"]
    for key in ["readme", "current_state"]:
        entrypoint = (project_root / entrypoints[key]).resolve()
        if not within(entrypoint, project_root):
            errors.append(f"entrypoint escapes project root: {entrypoints[key]}")
        elif not entrypoint.is_file():
            errors.append(f"missing project entrypoint: {entrypoints[key]}")
        else:
            check_meta(entrypoint, manifest, errors)
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["preflight", "validate"], default="validate")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--package-dir", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.mode == "preflight":
        project_root, package_dir, errors = preflight(args.project_root, args.package_dir)
        if errors:
            print("PREFLIGHT FAILED")
            for error in errors:
                print(f"- {error}")
            return 1
        print("PREFLIGHT PASSED")
        print(f"project_root={project_root}")
        print(f"package_dir={package_dir}")
        return 0

    errors = validate_package(args.project_root, args.package_dir)
    if errors:
        print("PACKAGE VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PACKAGE VALIDATION PASSED")
    print(f"project_root={Path(args.project_root).resolve()}")
    print(f"package_dir={Path(args.package_dir)}")
    print("scope=path, shape, source roles, state coherence, closure bookkeeping, entrypoint agreement, rendered tables, readable HTML, visible diagrams")
    return 0


if __name__ == "__main__":
    sys.exit(main())
