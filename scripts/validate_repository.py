#!/usr/bin/env python3
"""Validate the candidate pre-development framework repository.

This script checks repository structure and machine-readable templates. It does
not claim that the framework is effective; scenario and project validation are
separate evidence.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "README.md",
    "FRAMEWORK.md",
    "VERSION",
    "CHANGELOG.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "docs/quickstart.md",
    "docs/compatibility.md",
    "docs/public-release.md",
    "profiles/software-risks.md",
    ".github/workflows/validate.yml",
    "scripts/new_package.py",
    "scripts/package_versions.py",
    "scripts/check_all.py",
    "scripts/test_new_package.py",
    "validation/candidate-0.10.2-public-readiness.md",
    "protocol/lifecycle.md",
    "protocol/change-and-evidence.md",
    "protocol/machine-contract.md",
    "templates/delivery-plan.json",
    "schemas/delivery-plan.schema.json",
    "scripts/validate_legacy_package.py",
    "scripts/test_current_package.py",
    "protocol/artifact-contract.md",
    "protocol/output-management.md",
    "protocol/source-governance.md",
    "protocol/clarification-and-baseline.md",
    "protocol/project-entrypoints.md",
    "protocol/development-ready.md",
    "protocol/self-validation.md",
    "routing/route-selection.md",
    "routing/context-profile.md",
    "templates/00-intake-and-context.md",
    "templates/00-project-context.json",
    "templates/package-manifest.json",
    "templates/01-intent-and-scope.md",
    "templates/02-requirements-and-business-model.md",
    "templates/03-module-card.md",
    "templates/04-interaction-catalog.json",
    "templates/05-architecture-and-contracts.md",
    "templates/06-delivery-slice.md",
    "templates/07-development-task.json",
    "templates/08-integration-and-acceptance.md",
    "templates/09-traceability-matrix.md",
    "templates/10-self-validation-report.md",
    "templates/development-ready-document.md",
    "templates/project-README.md",
    "templates/project-current-state.md",
    "schemas/project-context.schema.json",
    "schemas/package-manifest.schema.json",
    "schemas/interaction-catalog.schema.json",
    "schemas/development-task.schema.json",
    "checklists/system-view-matrix.md",
    "checklists/interaction-review.md",
    "checklists/consistency-review.md",
    "checklists/model-autonomy-review.md",
    "evals/README.md",
    "validation/framework-validation-plan.md",
    "validation/initial-self-audit.md",
    "validation/candidate-2-output-management-audit.md",
    "validation/candidate-4-communication-visual-audit.md",
    "validation/candidate-5-readable-delivery-audit.md",
    "integrations/generic/ENTRY.md",
    "integrations/codex/README.md",
    "scripts/validate_project_package.py",
    "scripts/render_readable_package.py",
    "scripts/test_project_package_validator.py",
]

TEMPLATE_SCHEMA_PAIRS = [
    ("templates/quick-input.json", "schemas/quick-input.schema.json"),
    ("templates/delivery-plan.json", "schemas/delivery-plan.schema.json"),
    ("templates/00-project-context.json", "schemas/project-context.schema.json"),
    ("templates/package-manifest.json", "schemas/package-manifest.schema.json"),
    ("templates/04-interaction-catalog.json", "schemas/interaction-catalog.schema.json"),
    ("templates/07-development-task.json", "schemas/development-task.schema.json"),
]

REQUIRED_EVALS = {
    "EVAL-001": "轻量",
    "EVAL-002": "标准",
    "EVAL-003": "完整",
    "EVAL-004": "完整",
    "EVAL-005": "完整",
    "EVAL-006": "Invalid Input",
    "EVAL-007": "路径",
    "EVAL-008": "旧",
    "EVAL-009": "回写",
    "EVAL-010": "Ready",
    "EVAL-011": "通信",
    "EVAL-012": "阅览版",
    "EVAL-013": "standard",
    "EVAL-014": "团队",
    "EVAL-015": "授权",
    "EVAL-016": "delta",
    "EVAL-017": "project_id",
    "EVAL-018": "CLI",
    "EVAL-019": "HTML",
}

FORBIDDEN_ACTIVE_DIRECTIVES = [
    re.compile(r"必须使用.{0,12}Skill"),
    re.compile(r"必须使用.{0,12}Agent"),
    re.compile(r"必须调用.{0,12}Skill"),
]


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def check_files(errors: list[str]) -> None:
    for relative in REQUIRED_FILES:
        if not (ROOT / relative).is_file():
            fail(errors, f"missing required file: {relative}")


def check_version(errors: list[str]) -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    for relative in ["README.md", "FRAMEWORK.md", "CHANGELOG.md", "validation/framework-validation-plan.md"]:
        text = (ROOT / relative).read_text(encoding="utf-8")
        if version not in text:
            fail(errors, f"version {version!r} not referenced in {relative}")

    for relative in ["templates/00-project-context.json", "templates/package-manifest.json"]:
        template = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        if template.get("framework_version") != version:
            fail(errors, f"framework version mismatch in {relative}")

    for relative in [
        "templates/development-ready-document.md",
    ]:
        text = (ROOT / relative).read_text(encoding="utf-8")
        if f"framework_version={version}" not in text:
            fail(errors, f"framework version mismatch in {relative}")


def check_markdown_links(errors: list[str]) -> None:
    link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for path in ROOT.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        for target in link_pattern.findall(text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            clean_target = target.split("#", 1)[0]
            if not clean_target:
                continue
            resolved = (path.parent / clean_target).resolve()
            if not resolved.exists():
                fail(errors, f"broken link in {path.relative_to(ROOT)}: {target}")


def check_schemas(errors: list[str]) -> None:
    for template_rel, schema_rel in TEMPLATE_SCHEMA_PAIRS:
        template_path = ROOT / template_rel
        try:
            template = json.loads(template_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            fail(errors, f"cannot parse JSON {template_rel}: {exc}")
            continue
        schema = json.loads((ROOT / schema_rel).read_text(encoding="utf-8"))
        validate_schema_subset(template, schema, template_rel, errors)


def validate_schema_subset(
    value: object,
    schema: dict[str, object],
    source: str,
    errors: list[str],
    location: str = "<root>",
) -> None:
    """Validate the JSON Schema keywords used by this repository.

    The candidate repository intentionally avoids package installation. This
    small validator covers only the explicit keywords present in our schemas.
    """

    expected_type = schema.get("type")
    type_map = {
        "object": dict,
        "array": list,
        "string": str,
        "boolean": bool,
    }
    if expected_type in type_map and not isinstance(value, type_map[expected_type]):
        fail(errors, f"schema mismatch {source} at {location}: expected {expected_type}")
        return

    if "const" in schema and value != schema["const"]:
        fail(errors, f"schema mismatch {source} at {location}: expected constant {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        fail(errors, f"schema mismatch {source} at {location}: {value!r} not in enum")
    if isinstance(value, str):
        if "minLength" in schema and len(value) < int(schema["minLength"]):
            fail(errors, f"schema mismatch {source} at {location}: string is too short")
        if "pattern" in schema and re.search(str(schema["pattern"]), value) is None:
            fail(errors, f"schema mismatch {source} at {location}: does not match {schema['pattern']!r}")

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                fail(errors, f"schema mismatch {source} at {location}: missing key {key}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    fail(errors, f"schema mismatch {source} at {location}: unexpected key {key}")
        for key, child_schema in properties.items():
            if key in value:
                child_location = key if location == "<root>" else f"{location}.{key}"
                validate_schema_subset(value[key], child_schema, source, errors, child_location)

    if isinstance(value, list):
        if "minItems" in schema and len(value) < int(schema["minItems"]):
            fail(errors, f"schema mismatch {source} at {location}: array is too short")
        if schema.get("uniqueItems") is True:
            serialized = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in value]
            if len(serialized) != len(set(serialized)):
                fail(errors, f"schema mismatch {source} at {location}: array items are not unique")
        if "items" in schema:
            for index, item in enumerate(value):
                child_location = f"{location}[{index}]"
                validate_schema_subset(item, schema["items"], source, errors, child_location)


def check_evals(errors: list[str]) -> None:
    eval_dir = ROOT / "evals" / "cases"
    files = {path.stem: path for path in eval_dir.glob("EVAL-*.md")}
    for eval_id, marker in REQUIRED_EVALS.items():
        matches = [path for stem, path in files.items() if stem.startswith(eval_id)]
        if not matches:
            fail(errors, f"missing eval: {eval_id}")
            continue
        content = matches[0].read_text(encoding="utf-8")
        if marker not in content:
            fail(errors, f"eval {eval_id} missing expected marker: {marker}")
        for heading in ["## 输入", "## 通过条件", "## 硬性失败"]:
            if heading not in content:
                fail(errors, f"eval {eval_id} missing section: {heading}")


def check_boundaries(errors: list[str]) -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    framework = (ROOT / "FRAMEWORK.md").read_text(encoding="utf-8")
    required_phrases = [
        "不生成正式业务代码",
        "不规定后续开发必须使用什么模型、Skill、Agent、工具、编码方法或内部实现",
        "Development Ready",
        "显式调用",
    ]
    combined = readme + "\n" + framework
    for phrase in required_phrases:
        if phrase not in combined:
            fail(errors, f"missing boundary phrase: {phrase}")

    # These patterns are permitted in examples that explicitly reject them, but
    # they must not appear as active requirements in protocol or routing files.
    governed_paths = list((ROOT / "protocol").glob("*.md")) + list((ROOT / "routing").glob("*.md"))
    for path in governed_paths:
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_ACTIVE_DIRECTIVES:
            for match in pattern.finditer(text):
                context = text[max(0, match.start() - 30): match.end() + 30]
                if any(negation in context for negation in ["不规定", "没有要求", "不得", "不允许", "不需要"]):
                    continue
                fail(errors, f"possible executor constraint in {path.relative_to(ROOT)}: {match.group(0)}")


def check_output_management(errors: list[str]) -> None:
    manifest_path = ROOT / "templates" / "package-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    expected_directory = f"{manifest['package_id']}-{manifest['package_slug']}"
    if expected_directory != "REQ-001-requirement-short-name":
        fail(errors, "package manifest id and slug do not form the documented directory name")

    seen_paths: set[str] = set()
    if not manifest["artifacts"]:
        fail(errors, "package manifest must list at least one artifact")
    for raw_path in manifest["artifacts"]:
        parsed = PurePosixPath(raw_path)
        if parsed.is_absolute() or ".." in parsed.parts or "\\" in raw_path:
            fail(errors, f"unsafe artifact path in package manifest: {raw_path}")
        normalized = raw_path.casefold()
        if normalized in seen_paths:
            fail(errors, f"duplicate artifact path in package manifest: {raw_path}")
        seen_paths.add(normalized)

    if manifest["primary_artifact"] not in manifest["artifacts"]:
        fail(errors, "primary artifact must appear in package manifest artifacts")

    readable_artifact = manifest.get("readable_artifact", "")
    if manifest["route"] in {"standard", "complete"} and not readable_artifact:
        fail(errors, f"{manifest['route']}-route package template requires readable_artifact")
    if readable_artifact and readable_artifact not in manifest["artifacts"]:
        fail(errors, "readable artifact must appear in package manifest artifacts")

    source_policy = manifest["source_policy"]
    source_roles = [
        set(source_policy["authoritative_sources"]),
        set(source_policy["supporting_sources"]),
        set(source_policy["excluded_sources"]),
    ]
    if any(source_roles[left] & source_roles[right] for left in range(3) for right in range(left + 1, 3)):
        fail(errors, "package manifest source roles must be mutually exclusive")

    for key in ("context_artifact", "plan_artifact"):
        if manifest[key] not in manifest["artifacts"]:
            fail(errors, f"{key} must appear in artifacts")
    if "project_root" in manifest:
        fail(errors, "current manifest must not persist a machine root")

    unexpected_manifests = [
        path.relative_to(ROOT)
        for path in ROOT.rglob("package-manifest.json")
        if path != manifest_path and "examples" not in path.relative_to(ROOT).parts
    ]
    for path in unexpected_manifests:
        fail(errors, f"project package manifest misplaced in framework repository: {path}")


def main() -> int:
    errors: list[str] = []
    check_files(errors)
    if not errors:
        check_version(errors)
        check_markdown_links(errors)
        check_schemas(errors)
        check_evals(errors)
        check_boundaries(errors)
        check_output_management(errors)

    if errors:
        print("VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1

    markdown_count = sum(1 for _ in ROOT.rglob("*.md"))
    eval_count = sum(1 for _ in (ROOT / "evals" / "cases").glob("EVAL-*.md"))
    print("VALIDATION PASSED")
    print(f"root={ROOT}")
    print(f"markdown_files={markdown_count}")
    print(f"eval_cases={eval_count}")
    print(f"schema_template_pairs={len(TEMPLATE_SCHEMA_PAIRS)}")
    print("scope=structural integrity only; real-project effectiveness not yet proven")
    return 0


if __name__ == "__main__":
    sys.exit(main())
