#!/usr/bin/env python3
"""Validate package bookkeeping, never substitute for semantic review or approval."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
from html.parser import HTMLParser

from validate_repository import validate_schema_subset
from validate_legacy_package import preflight, build_parser, within
from package_versions import CURRENT_VERSION, SUPPORTED_CURRENT_VERSIONS

ROOT = Path(__file__).resolve().parents[1]
VERSION = CURRENT_VERSION
LEGACY_VERSION = '0.9.0-candidate.5'


def local_path(base, raw, errors, label):
    parsed = PurePosixPath(raw)
    if (not raw or raw == '.' or parsed.is_absolute() or '..' in parsed.parts
            or '\\' in raw or ':' in raw or '?' in raw or '#' in raw):
        errors.append(f'{label}: unsafe relative path {raw!r}')
        return None
    path = (base / raw).resolve()
    if not within(path, base) or path == base:
        errors.append(f'{label}: path escapes directory: {raw}')
        return None
    if not path.is_file():
        errors.append(f'{label}: missing file: {raw}')
        return None
    return path


def read_json(path, schema_name, errors):
    if path is None:
        return None
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        errors.append(f'cannot read JSON {path.name}: {exc}')
        return None
    schema = json.loads((ROOT / 'schemas' / schema_name).read_text(encoding='utf-8'))
    before = len(errors)
    validate_schema_subset(value, schema, path.name, errors)
    return value if len(errors) == before else None


def indexed(items, label, errors, key='id'):
    result = {}
    for item in items:
        identifier = item[key]
        if identifier in result:
            errors.append(f'duplicate {label} ID: {identifier}')
        result[identifier] = item
    return result


def references(values, catalog, label, errors):
    for value in values:
        if value not in catalog:
            errors.append(f'{label}: unknown reference {value}')


def timestamp(value, label, errors):
    try:
        datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        errors.append(f'{label}: use ISO date or datetime')


def check_sources(manifest, plan, errors):
    sources = indexed(manifest['sources'], 'source', errors, 'source_id')
    roles = [set(manifest['source_policy'][key]) for key in
             ('authoritative_sources', 'supporting_sources', 'excluded_sources')]
    for role in roles:
        references(role, sources, 'source policy', errors)
    if any(roles[i] & roles[j] for i in range(3) for j in range(i+1, 3)):
        errors.append('source roles must be mutually exclusive')
    if set(sources) != set.union(*roles):
        errors.append('every source must have one explicit role')
    if not roles[0]:
        errors.append('at least one authoritative source is required')
    for source in sources.values():
        timestamp(source['checked_at'], source['source_id'], errors)
    for requirement in plan['requirements']:
        normative = {sid for sid in requirement['source_ids'] if sid in sources and sources[sid]['kind'] == 'normative'}
        if not normative & roles[0]:
            errors.append(f"{requirement['id']}: requires an authoritative normative source for desired behavior")
        references(requirement['source_ids'], sources, requirement['id'], errors)
        if set(requirement['source_ids']) & roles[2]:
            errors.append(f"{requirement['id']}: excluded source cannot justify a requirement")
    for closure in manifest['clarification_closures']:
        references([closure['answer_source']], sources, 'clarification answer', errors)
        if not set(closure['affected_ids']) <= set(closure['updated_ids']):
            errors.append('clarification closure is missing affected IDs in updated_ids')
    if manifest['mode'] in {'enhancement', 'delta'} and not manifest['baseline_refs']:
        errors.append('enhancement/delta requires explicit baseline_refs')
    if manifest['mode'] == 'delta' and not plan['changes']:
        errors.append('delta requires an explicit change ledger')


def check_plan(manifest, context, plan, errors):
    reqs = indexed(plan['requirements'], 'requirement', errors)
    acs = indexed(plan['acceptance'], 'acceptance', errors)
    contracts = indexed(plan['contracts'], 'contract', errors)
    tasks = indexed(plan['tasks'], 'task', errors)
    slices = indexed(plan['slices'], 'slice', errors)
    team = indexed(context['team'], 'member', errors, 'member_id')
    if context['project_id'] != manifest['project_id']:
        errors.append('context project_id must match manifest')
    if context['framework_version'] != manifest['framework_version']:
        errors.append('context framework_version must match manifest')
    if context['assignment_policy'] == 'fixed' and context['suggested_changes']:
        errors.append('fixed assignment policy cannot contain proposed reassignments')
    for change in context['suggested_changes']:
        references([change['member_id']], team, 'suggested assignment', errors)
    all_ids = [x['id'] for k in ('requirements','acceptance','contracts','tasks','slices') for x in plan[k]]
    if len(all_ids) != len(set(all_ids)):
        errors.append('stable IDs must be unique across plan catalogs')
    for req in reqs.values():
        references(req['acceptance_ids'], acs, req['id'], errors)
    membership = []
    for sl in slices.values():
        references(sl['task_ids'], tasks, sl['id'], errors)
        membership.extend(sl['task_ids'])
        for task_id in sl['task_ids']:
            if task_id in tasks and tasks[task_id]['slice_id'] != sl['id']:
                errors.append(f'{task_id}: slice membership mismatch')
    if sorted(membership) != sorted(tasks):
        errors.append('every task must belong to exactly one slice')
    for task in tasks.values():
        tid = task['id']
        references(task['requirements'], reqs, tid, errors)
        references(task['acceptance_ids'], acs, tid, errors)
        references(task['contracts'], contracts, tid, errors)
        references(task['depends_on'], tasks, tid, errors)
        references([task['slice_id']], slices, tid, errors)
        references(task['collaborators'], team, tid, errors)
        if task['owner']:
            references([task['owner']], team, tid, errors)
        valid_acs = {ac for rid in task['requirements'] if rid in reqs for ac in reqs[rid]['acceptance_ids']}
        if not set(task['acceptance_ids']) <= valid_acs:
            errors.append(f'{tid}: acceptance must belong to its requirements')
    # Iterative topological elimination avoids recursion limits on large packages.
    pending = {tid: set(t['depends_on']) & tasks.keys() for tid,t in tasks.items()}
    while pending:
        available = {tid for tid,deps in pending.items() if not deps}
        if not available:
            errors.append('task dependency cycle detected')
            break
        pending = {tid: deps - available for tid,deps in pending.items() if tid not in available}
    for contract in contracts.values():
        if contract['owner']:
            references([contract['owner']], team, contract['id'], errors)
    for change in plan['changes']:
        references(change['affected_tasks'], tasks, 'change impact', errors)
        if change['kind'] in {'added','changed','unchanged'}:
            references([change['id']], set(all_ids), 'change ledger', errors)
        if change['kind'] in {'added','changed'} and not change['affected_tasks']:
            errors.append('added/changed items require affected_tasks')
    # Per-slice quality and authorization are independent of global quality.
    authorized = set()
    for sl in slices.values():
        sid = sl['id']
        quality = sl['readiness']
        if quality == 'ready' and (sl['blockers'] or sl['conditions']):
            errors.append(f'{sid}: ready slice cannot have blockers or conditions')
        if quality == 'conditionally_ready' and (sl['blockers'] or not sl['conditions']):
            errors.append(f'{sid}: conditional slice needs conditions and no blockers')
        indexed(sl['conditions'], 'condition', errors)
        for condition in sl['conditions']:
            references([condition['owner']], team, 'condition owner', errors)
            references(condition['invalidated_tasks'], tasks, 'condition invalidation', errors)
            timestamp(condition['decision_by'], 'condition deadline', errors)
            if not set(condition['invalidated_tasks']) <= set(sl['task_ids']):
                errors.append(f'{sid}: condition isolation spans other slices')
        if quality in {'ready','conditionally_ready'}:
            for role in ('integration_owner','acceptance_owner'):
                references([sl[role]], team, f'{sid} {role}', errors)
            for tid in sl['task_ids']:
                if tid not in tasks: continue
                task = tasks[tid]
                owner = team.get(task['owner'])
                if owner is None or task['responsibility'] not in owner['confirmed_responsibilities']:
                    errors.append(f'{tid}: ready task requires owner with confirmed responsibility')
                for cid in task['contracts']:
                    contract = contracts.get(cid)
                    if contract and (contract['state'] != 'confirmed' or not contract['owner']):
                        errors.append(f'{tid}: ready task requires confirmed, owned contracts')
        if sl['authorized']:
            authorized.update(sl['task_ids'])
            if quality not in {'ready','conditionally_ready'}:
                errors.append(f'{sid}: cannot authorize an unready slice')
            if any(c['high_consequence'] for c in sl['conditions']):
                errors.append(f'{sid}: high-consequence condition blocks authorization')
            if 'approval' not in sl:
                errors.append(f'{sid}: authorized slice requires approval evidence')
        if 'approval' in sl:
            if sl['approval']['approved_package_version'] != manifest['package_version']:
                errors.append('approval package version is stale')
            timestamp(sl['approval']['approved_at'], 'approval date', errors)
    for tid in authorized:
        if tid in tasks and not set(tasks[tid]['depends_on']) <= authorized:
            errors.append(f'{tid}: authorized dependency closure is incomplete')
    if set(manifest['authorized_work']) != authorized:
        errors.append('authorized_work must exactly equal authorized slices tasks')
    scope = manifest['development_scope']
    baseline = manifest['baseline_status']
    if authorized and baseline != 'approved':
        errors.append('only approved baseline can authorize work')
    if scope == 'none' and authorized or scope != 'none' and not authorized:
        errors.append('development_scope disagrees with authorized_work')
    if scope == 'full' and authorized != set(tasks):
        errors.append('full scope requires all package tasks authorized')
    if baseline == 'approved' and not any('approval' in sl for sl in slices.values()):
        errors.append('approved baseline requires recorded slice approval')
    if baseline == 'superseded' and scope != 'none':
        errors.append('superseded package cannot authorize work')
    quality = manifest['readiness']
    if quality in {'invalid_input','not_assessed'} and scope != 'none':
        errors.append('invalid/unassessed package cannot authorize work')
    if quality in {'ready','conditionally_ready'}:
        if not tasks or not reqs or not acs or not slices:
            errors.append('ready package requires nonempty requirements, tasks, acceptance and slices')
        accepted = {'ready'} if quality == 'ready' else {'ready','conditionally_ready'}
        if any(sl['readiness'] not in accepted for sl in slices.values()):
            errors.append('package quality overstates slice quality')
        used_acs = {ac for req in reqs.values() for ac in req['acceptance_ids']}
        if set(acs) != used_acs:
            errors.append('acceptance catalog has orphan entries')
    # A blocked package may still contain ready slices. Every acceptance of a
    # requirement touched by such a slice needs an explicit task, including
    # tasks in blocked slices. Do not make unrelated draft requirements a gate.
    ready_tasks = {tid for sl in slices.values()
                   if sl['readiness'] in {'ready', 'conditionally_ready'}
                   for tid in sl['task_ids'] if tid in tasks}
    checked_requirements = (set(reqs) if quality in {'ready', 'conditionally_ready'} else
                            {rid for tid in ready_tasks for rid in tasks[tid]['requirements']})
    for rid in checked_requirements & reqs.keys():
        covered = {ac for t in tasks.values() if rid in t['requirements'] for ac in t['acceptance_ids']}
        if not set(reqs[rid]['acceptance_ids']) <= covered:
            errors.append(f'{rid}: acceptance coverage is incomplete; map remaining acceptance to explicit tasks/slices')
    for tid in ready_tasks:
        for rid in set(tasks[tid]['requirements']) & reqs.keys():
            if not set(tasks[tid]['acceptance_ids']) & set(reqs[rid]['acceptance_ids']):
                errors.append(f'{tid}: ready task needs acceptance for each referenced requirement: {rid}')


class ImageSources(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sources = set()

    def handle_starttag(self, tag, attrs):
        if tag == 'img':
            self.sources.update(value for key, value in attrs if key == 'src')


def validate_current(project_root, package_dir, errors):
    manifest = read_json(package_dir / 'package-manifest.json', 'package-manifest.schema.json', errors)
    if manifest is None: return errors
    actual = package_dir.relative_to(project_root).as_posix()
    if manifest['package_path'] != actual:
        errors.append('manifest package_path mismatch')
    if package_dir.name != f"{manifest['package_id']}-{manifest['package_slug']}":
        errors.append('package directory name mismatch')
    files = {}
    resolved_seen = set()
    for raw in manifest['artifacts']:
        path = local_path(package_dir, raw, errors, 'artifact')
        if path:
            normalized = str(path).casefold()
            if normalized in resolved_seen:
                errors.append(f'duplicate artifact path: {raw}')
            resolved_seen.add(normalized)
            files[raw] = path
    for key in ('primary_artifact','context_artifact','plan_artifact'):
        if manifest[key] not in files:
            errors.append(f'{key} must be a listed existing artifact')
    if errors: return errors
    context = read_json(files[manifest['context_artifact']], 'project-context.schema.json', errors)
    plan = read_json(files[manifest['plan_artifact']], 'delivery-plan.schema.json', errors)
    if context is None or plan is None: return errors
    check_sources(manifest, plan, errors)
    check_plan(manifest, context, plan, errors)
    primary = files[manifest['primary_artifact']]
    if primary.parent != package_dir:
        errors.append('primary Markdown must be in package root')
    if primary.suffix != '.md':
        errors.append('primary_artifact must be Markdown')
    prose = primary.read_text(encoding='utf-8')
    # Only package-local summary carries metadata, never shared project entrypoints.
    from validate_legacy_package import check_meta
    check_meta(primary, manifest, errors)
    link_re = re.compile(r'(?<!!)\[[^\]]+\]\(([^)]+)\)')
    for raw in manifest['entrypoints']:
        path = local_path(project_root, raw, errors, 'entrypoint')
        if not path: continue
        targets = []
        for target in link_re.findall(path.read_text(encoding='utf-8')):
            target = target.strip('<>')
            parsed = urlsplit(target)
            if not parsed.scheme and not parsed.netloc:
                targets.append((path.parent / unquote(parsed.path)).resolve())
        if not any(target in {primary, package_dir / 'package-manifest.json'} for target in targets):
            errors.append(f'entrypoint must link this package: {raw}')
    if manifest['complex_relationships'] and not manifest['diagrams']:
        errors.append('complex relationships require visible diagrams')
    for diagram in manifest['diagrams']:
        for field in ('source','image'):
            if diagram[field] not in files:
                errors.append(f'diagram {field} must be a listed artifact')
        if not re.search(r'!\[[^\]]*\]\(' + re.escape(diagram['image']) + r'\)', prose):
            errors.append('diagram image must be visible in primary document')
        if Path(diagram['image']).suffix.lower() not in {'.svg','.png','.jpg','.jpeg','.webp'}:
            errors.append('diagram image must use a supported image format')
    readable = manifest['readable_artifact']
    if manifest['route'] != 'light' and not readable and 'readable_waiver' not in manifest:
        errors.append('standard/complete requires readable HTML or evidenced readable_waiver')
    if readable:
        if readable not in files or files[readable].suffix != '.html':
            errors.append('readable_artifact must be a listed HTML file')
        elif files[readable].parent != primary.parent:
            errors.append('readable HTML must be beside primary Markdown')
        else:
            from render_readable_package import build_html, package_fingerprint
            actual_html = files[readable].read_text(encoding='utf-8')
            try:
                expected_hash = package_fingerprint(primary, prose)
                if f'predev-source-sha256: {expected_hash}' not in actual_html:
                    errors.append('readable HTML is stale; regenerate after source/plan/diagram/manifest changes')
                expected = build_html(primary, prose)
                if actual_html != expected:
                    errors.append('readable HTML body differs or document shell differs from current derived content; regenerate the complete HTML')
                images = ImageSources()
                images.feed(actual_html)
                for diagram in manifest['diagrams']:
                    if diagram['image'] not in images.sources:
                        errors.append(f"diagram is not rendered as an image in readable HTML: {diagram['image']}")
            except (OSError, ValueError) as exc:
                errors.append(f'cannot verify readable source: {exc}')
    return errors


def validate_package(project_root_raw, package_dir_raw):
    project_root, package_dir, errors = preflight(project_root_raw, package_dir_raw)
    if errors: return errors
    if not within((package_dir / 'package-manifest.json').resolve(), package_dir):
        return ['manifest escapes package directory']
    try:
        raw = json.loads((package_dir / 'package-manifest.json').read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        return [f'cannot read package manifest: {exc}']
    if not isinstance(raw, dict): return ['package manifest must be an object']
    version = raw.get('framework_version')
    if version == LEGACY_VERSION:
        if sys.platform == 'win32':
            return ['frozen 0.9 package format requires POSIX project_root; migrate explicitly to current format before Windows validation']
        from validate_legacy_package import validate_package as legacy
        return legacy(project_root_raw, package_dir_raw)
    if version not in SUPPORTED_CURRENT_VERSIONS:
        return [f'unsupported framework_version: {version!r}; explicit migration required']
    try:
        return validate_current(project_root, package_dir, errors)
    except (OSError, UnicodeError) as exc:
        errors.append(f'cannot read package artifact: {exc}')
        return errors


def main():
    args = build_parser().parse_args()
    if args.mode == 'preflight':
        _, _, errors = preflight(args.project_root, args.package_dir)
    else:
        errors = validate_package(args.project_root, args.package_dir)
    print('VALIDATION FAILED' if errors else 'VALIDATION PASSED')
    for error in errors: print(f'- {error}')
    print('scope=structure, references, ownership, state, authorization bookkeeping and derived freshness; semantic truth and approval authenticity require review')
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
