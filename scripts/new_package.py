#!/usr/bin/env python3
"""Initialize a light/new draft from one brief. Never grant development authority."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from package_versions import CURRENT_VERSION
from render_readable_package import build_html
from validate_legacy_package import preflight, within
from validate_repository import validate_schema_subset
from validate_project_package import check_plan, check_sources

ROOT = Path(__file__).resolve().parents[1]


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def prepare(project_root_raw, brief_raw):
    brief_path = Path(brief_raw).resolve()
    raw = brief_path.read_bytes()
    brief = json.loads(raw.decode('utf-8'))
    errors = []
    schema = json.loads((ROOT/'schemas/quick-input.schema.json').read_text(encoding='utf-8'))
    validate_schema_subset(brief, schema, 'quick input', errors)
    if errors:
        raise ValueError('\n'.join(errors))
    package_path = f"docs/pre-development/{brief['package_id']}-{brief['package_slug']}"
    root, package, errors = preflight(project_root_raw, package_path)
    if errors:
        raise ValueError('\n'.join(errors))
    if package.exists() or package.is_symlink():
        raise ValueError('package already exists; no files were overwritten')
    index = root/'docs/pre-development/index.md'
    if not within(index.resolve(), root) or index.is_symlink():
        raise ValueError('index path escapes the project or is a symbolic link')
    if index.resolve() == brief_path:
        raise ValueError('input brief cannot also be the output index')
    if index.exists() and not index.is_file():
        raise ValueError('index path is not a file')
    # Read before writing so malformed UTF-8 does not create a partial draft.
    if index.exists():
        index.read_text(encoding='utf-8')
    manifest = json.loads((ROOT/'templates/package-manifest.json').read_text(encoding='utf-8'))
    manifest.update(project_id=brief['project_id'],package_id=brief['package_id'],
                    package_slug=brief['package_slug'],package_path=package_path,route='light',
                    route_reason='轻量初始化请求；尚未核实风险，评审发现高后果变化时须升级路线。')
    manifest['sources'][0].update(locator='input-brief.json',revision='sha256:'+hashlib.sha256(raw).hexdigest(),
                                  checked_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
                                  scope='本次显式提供的需求输入，仍需核对现状与冲突',
                                  invalidated_by='需求、验收、来源或适用范围变化')
    manifest['artifacts'].append('input-brief.json')
    context = json.loads((ROOT/'templates/00-project-context.json').read_text(encoding='utf-8'))
    context.update(project_id=brief['project_id'],team=brief.get('team',[]),
                   unknowns=['待核实需求来源、实现现状、风险路线、团队职责和验收充分性。'])
    validate_schema_subset(context,json.loads((ROOT/'schemas/project-context.schema.json').read_text(encoding='utf-8')),
                           'project context',errors)
    owner = brief.get('owner','')
    acceptance = [dict(id=f'AC-{i}',**ac) for i,ac in enumerate(brief['acceptance'],1)]
    plan = dict(requirements=[dict(id='REQ-F1',statement=brief['goal'],source_ids=['SRC-001'],
                                   acceptance_ids=[ac['id'] for ac in acceptance])],
                acceptance=acceptance,contracts=[],changes=[],
                tasks=[dict(id='DEV-1',title=brief['title'],objective=brief['goal'],scope=brief['scope'],
                            non_goals=brief['non_goals'],requirements=['REQ-F1'],
                            acceptance_ids=[ac['id'] for ac in acceptance],contracts=[],depends_on=[],
                            owner=owner,responsibility='implementation',collaborators=[],slice_id='SLICE-1')],
                slices=[dict(id='SLICE-1',task_ids=['DEV-1'],readiness='not_assessed',blockers=[],conditions=[],
                             authorized=False,integration_owner=owner,acceptance_owner=owner)])
    if errors:
        raise ValueError('\n'.join(errors))
    check_sources(manifest,plan,errors)
    check_plan(manifest,context,plan,errors)
    if errors:
        raise ValueError('\n'.join(errors))
    meta = '; '.join(f'{key}={manifest[key]}' for key in
                     ('framework_version','package_id','package_version','baseline_status','readiness','development_scope'))
    markdown = (f"# {brief['title']}\n\n<!-- predev-meta: {meta} -->\n\n"
                '> 自动生成的轻量新需求草稿。材料尚未评估，没有批准或开发授权。\n\n'
                '## 输入与范围\n\n'
                'SRC-001 是 input-brief.json 的原始输入快照；当前结构化需求、范围、任务和验收见 delivery-plan.json。\n\n'
                '## 待完成的核对\n\n'
                '- 定位当前代码或资源，分别核实期望与现状。\n'
                '- 确认是否涉及权限、资金、数据不可逆变化或新契约；必要时升级风险路线。\n'
                '- 确认任务所有权、验收充分性，以及不适用视图的理由。\n'
                '- 完成适用自验后再评估就绪度；责任人的批准与开发授权另行记录。\n\n'
                '## 交付与边界\n\n'
                '阅读版由本文件、清单及结构化计划派生。字段通过检查只代表草稿结构有效。\n')
    files = {'input-brief.json':raw,'package-manifest.json':json_text(manifest).encode('utf-8'),
             'project-context.json':json_text(context).encode('utf-8'),
             'delivery-plan.json':json_text(plan).encode('utf-8'),'development-ready.md':markdown.encode('utf-8')}
    return root,package,index,brief,files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root',required=True)
    parser.add_argument('--brief',required=True)
    parser.add_argument('--dry-run',action='store_true')
    args = parser.parse_args()
    try:
        _,package,index,brief,files = prepare(args.project_root,args.brief)
        if args.dry_run:
            print(f'DRY RUN: create {package}; append navigation to {index}; no writes')
            return 0
        package.parent.mkdir(parents=True,exist_ok=True)
        package.mkdir()  # Existing packages are never replaced.
        for name,content in files.items():
            with (package/name).open('xb') as handle:
                handle.write(content)
        source=package/'development-ready.md'
        (package/'development-ready.html').write_text(build_html(source,source.read_text(encoding='utf-8')),encoding='utf-8')
        with index.open('a',encoding='utf-8') as handle:
            handle.write(f"\n[{brief['package_id']}]({package.name}/development-ready.md)\n")
        print(f'DRAFT CREATED: {package}')
        print(f'framework={CURRENT_VERSION}; mode=new; route=light; candidate + not_assessed + none')
        print('Next: review sources, risks, ownership and acceptance. No approval or development authority was created.')
        return 0
    except (OSError,ValueError) as exc:
        parser.exit(1,f'Cannot create draft: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
