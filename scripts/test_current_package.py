"""Synthetic package regressions. These do not measure model or project effectiveness."""
import copy
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from render_readable_package import build_html, split_table_row, render_inline
from validate_project_package import validate_package

FRAMEWORK = Path(__file__).resolve().parents[1]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sample(root, package_id='REQ-001'):
    manifest = json.loads((FRAMEWORK/'templates/package-manifest.json').read_text(encoding='utf-8'))
    manifest.update(package_id=package_id, package_slug='sample', readiness='ready',
                    route_reason='合成样例：已知输入输出的本地导出功能',
                    package_path=f'docs/pre-development/{package_id}-sample')
    manifest['sources'][0].update(locator='synthetic-prd.md', revision='fixture-v1',
                                  checked_at='2026-09-08', scope='本地任务导出',
                                  invalidated_by='输入字段、导出规则或输出格式发生变化')
    manifest['artifacts'].append('synthetic-prd.md')
    package = root / manifest['package_path']
    package.mkdir(parents=True)
    context = json.loads((FRAMEWORK/'templates/00-project-context.json').read_text(encoding='utf-8'))
    context.update(unknowns=[], team=[{'member_id':'M1','confirmed_responsibilities':['implementation','review'],
                    'availability':'每周三天（合成输入）','capabilities':['CLI','testing']}])
    plan = {
        'requirements':[{'id':'REQ-F1','statement':'将当前任务列表导出成本地 UTF-8 CSV。',
                         'source_ids':['SRC-001'],'acceptance_ids':['AC-1']}],
        'acceptance':[{'id':'AC-1','criterion':'给定空列表，输出只有表头的 UTF-8 CSV，返回成功且不访问网络。',
                       'method':'临时目录执行导出，对比文件字节与退出码。'}],
        'contracts':[],
        'tasks':[{'id':'DEV-1','title':'导出本地任务列表','objective':'交付空列表也可用的 CSV 导出',
                  'scope':['本地导出入口、编码和空列表处理'],'non_goals':['远程同步'],
                  'requirements':['REQ-F1'],'acceptance_ids':['AC-1'],'contracts':[],
                  'depends_on':[],'owner':'M1','responsibility':'implementation','collaborators':[],
                  'slice_id':'SLICE-1'}],
        'slices':[{'id':'SLICE-1','task_ids':['DEV-1'],'readiness':'ready','blockers':[],
                   'conditions':[],'authorized':False,'integration_owner':'M1','acceptance_owner':'M1'}],
        'changes':[]}
    (package/'synthetic-prd.md').write_text('# 合成输入\n空列表导出应产生仅含表头的 UTF-8 CSV。仅用于校验器回归，不是真实产品批准。\n', encoding='utf-8')
    index = root/'docs/pre-development/index.md'
    with index.open('a', encoding='utf-8') as handle:
        handle.write(f'\n[{package_id}]({package.name}/development-ready.md)\n')
    return package, manifest, context, plan


def materialize(package, manifest, context, plan, extra=''):
    write_json(package/'package-manifest.json', manifest)
    write_json(package/'project-context.json', context)
    write_json(package/'delivery-plan.json', plan)
    fields = ('framework_version','package_id','package_version','baseline_status','readiness','development_scope')
    meta = '; '.join(f'{k}={manifest[k]}' for k in fields)
    text = (f'# 合成开发准备包\n\n<!-- predev-meta: {meta} -->\n\n'
            '仅验证结构行为；本样例不是业务批准或跨项目有效性证据。\n\n'
            '目标：按 REQ-F1 导出当前本地任务，空列表保留表头。不包含远程同步。\n\n'
            '## 交付映射\n\n引用 delivery-plan.json；规则及验收见 REQ-F1、AC-1。\n\n'
            '| 情况 | 行为 |\n| --- | --- |\n| 空列表 | 仅表头，成功 |\n'+extra)
    (package/'development-ready.md').write_text(text, encoding='utf-8')
    # Generate a placeholder target before fingerprinting (readable target is excluded).
    (package/'development-ready.html').write_text('', encoding='utf-8')
    (package/'development-ready.html').write_text(build_html(package/'development-ready.md',text),encoding='utf-8')


def authorize(manifest, plan):
    manifest.update(baseline_status='approved', development_scope='full', authorized_work=[t['id'] for t in plan['tasks']])
    for sl in plan['slices']:
        sl['authorized'] = True
        sl['approval'] = {'approved_by':['synthetic-owner'],'approved_at':'2026-09-08',
                          'approved_package_version':manifest['package_version'],
                          'evidence':'合成批准，仅用于负例与正例回归，不授予真实开发权限。'}


class CurrentPackageTests(unittest.TestCase):
    def setUp(self):
        self.holder = tempfile.TemporaryDirectory()
        self.addCleanup(self.holder.cleanup)
        self.root = Path(self.holder.name)/'project'
        self.p, self.m, self.c, self.d = sample(self.root)

    def run_check(self):
        materialize(self.p,self.m,self.c,self.d)
        return validate_package(str(self.root),self.m['package_path'])

    def fails(self, fragment):
        errors = self.run_check()
        self.assertTrue(any(fragment in e for e in errors), errors)

    def test_candidate_ready_without_authority(self):
        self.assertEqual(self.run_check(),[])

    def test_approved_full(self):
        authorize(self.m,self.d)
        self.assertEqual(self.run_check(),[])

    def test_candidate_cannot_authorize(self):
        authorize(self.m,self.d)
        self.m['baseline_status']='candidate'
        self.fails('only approved')

    def test_approval_required(self):
        authorize(self.m,self.d)
        del self.d['slices'][0]['approval']
        self.fails('requires approval')

    def test_approval_version_pinned(self):
        authorize(self.m,self.d)
        self.m['package_version']='0.2.0'
        self.fails('approval package version is stale')

    def second_slice(self):
        second = copy.deepcopy(self.d['tasks'][0]); second.update(id='DEV-2',slice_id='SLICE-2')
        self.d['tasks'].append(second)
        sl = copy.deepcopy(self.d['slices'][0]); sl.update(id='SLICE-2',task_ids=['DEV-2'])
        self.d['slices'].append(sl)

    def blocked_slice(self):
        authorize(self.m,self.d)
        self.second_slice()
        self.d['slices'][1].update(readiness='not_ready',blockers=['等待新导出格式决策'],authorized=False)
        self.d['slices'][1].pop('approval',None)
        self.m.update(readiness='not_ready',development_scope='bounded')

    def test_independent_blocked_slice_does_not_stop_approved_slice(self):
        self.blocked_slice()
        self.assertEqual(self.run_check(),[])

    def test_dependency_on_blocked_slice_is_rejected(self):
        self.blocked_slice()
        self.d['tasks'][0]['depends_on']=['DEV-2']
        self.fails('dependency closure')

    def test_missing_reference(self):
        self.d['tasks'][0]['depends_on']=['DEV-MISSING']
        self.fails('unknown reference')

    def test_dependency_cycle(self):
        self.second_slice()
        self.d['tasks'][0]['depends_on']=['DEV-2']
        self.d['tasks'][1]['depends_on']=['DEV-1']
        self.fails('cycle')

    def test_empty_acceptance(self):
        self.d['tasks'][0]['acceptance_ids']=[]
        self.fails('array is too short')

    def test_uncovered_acceptance(self):
        self.d['acceptance'].append({'id':'AC-2','criterion':'含特殊字符时按 CSV 引号转义。','method':'文件比较'})
        self.d['requirements'][0]['acceptance_ids'].append('AC-2')
        self.fails('coverage is incomplete')

    def test_partial_authorization_still_checks_covered_requirement(self):
        self.blocked_slice()
        self.d['acceptance'].append({'id':'AC-2','criterion':'逗号字段正确转义','method':'字节比较'})
        self.d['requirements'][0]['acceptance_ids'].append('AC-2')
        self.fails('coverage is incomplete')

    def test_partial_requirement_may_map_remaining_acceptance_to_blocked_slice(self):
        self.blocked_slice()
        self.d['acceptance'].append({'id':'AC-2','criterion':'上传失败可重试','method':'契约测试'})
        self.d['requirements'][0]['acceptance_ids'].append('AC-2')
        self.d['tasks'][1]['acceptance_ids']=['AC-2']
        self.assertEqual(self.run_check(), [])

    def test_unrelated_draft_requirement_does_not_block_authorized_slice(self):
        self.blocked_slice()
        self.d['requirements'].append({'id':'REQ-DRAFT','statement':'待澄清需求',
                                      'source_ids':['SRC-001'],'acceptance_ids':['AC-DRAFT']})
        self.d['acceptance'].append({'id':'AC-DRAFT','criterion':'待澄清结果','method':'责任人复核'})
        self.assertEqual(self.run_check(), [])

    def test_ready_task_cannot_reference_requirement_without_its_acceptance(self):
        self.d['requirements'].append({'id':'REQ-2','statement':'第二个结果',
                                      'source_ids':['SRC-001'],'acceptance_ids':['AC-1']})
        self.d['acceptance'].append({'id':'AC-2','criterion':'第二个结果可见','method':'人工核对'})
        self.d['requirements'][1]['acceptance_ids']=['AC-2']
        self.second_slice()
        self.d['tasks'][1].update(requirements=['REQ-2'],acceptance_ids=['AC-2'])
        self.d['tasks'][0]['requirements'].append('REQ-2')
        self.fails('acceptance for each referenced requirement')

    def test_unknown_owner(self):
        self.d['tasks'][0]['owner']='M2'
        self.fails('unknown reference M2')

    def test_suggested_role_cannot_replace_confirmed_role(self):
        self.c['assignment_policy']='propose_changes'
        self.c['suggested_changes']=[{'member_id':'M1','proposal':'负责后端','reason':'需要'}]
        self.d['tasks'][0]['responsibility']='backend'
        self.fails('confirmed responsibility')

    def test_adjustable_team_two_members(self):
        self.c['team'].append({'member_id':'M2','confirmed_responsibilities':['review'],
                               'availability':'半天','capabilities':['testing']})
        self.d['slices'][0]['acceptance_owner']='M2'
        self.d['tasks'][0]['collaborators']=['M2']
        self.assertEqual(self.run_check(),[])

    def test_fixed_assignment_does_not_accept_implicit_reassignment(self):
        self.c['suggested_changes']=[{'member_id':'M1','proposal':'其他职责','reason':'方便'}]
        self.fails('fixed assignment')

    def test_missing_contract(self):
        self.d['tasks'][0]['contracts']=['CON-1']
        self.fails('unknown reference CON-1')

    def test_proposed_contract_is_not_ready(self):
        self.d['tasks'][0]['contracts']=['CON-1']
        self.d['contracts']=[{'id':'CON-1','owner':'M1','state':'proposed',
                             'definition':'调用现有任务导出接口','evidence':'候选文档'}]
        self.fails('confirmed, owned contracts')

    def test_duplicate_membership(self):
        self.second_slice()
        self.d['slices'][1]['task_ids'].append('DEV-1')
        self.fails('exactly one slice')

    def test_full_scope_must_include_all_tasks(self):
        self.blocked_slice()
        self.m['development_scope']='full'
        self.fails('all package tasks authorized')

    def test_conditionally_ready_without_authority(self):
        self.m['readiness']='conditionally_ready'
        self.d['slices'][0].update(readiness='conditionally_ready',conditions=[{
            'id':'COND-1','owner':'M1','decision_by':'2026-09-20','isolation':'导出提示文案独立于文件内容',
            'invalidated_tasks':['DEV-1'],'high_consequence':False}])
        self.assertEqual(self.run_check(),[])

    def test_high_consequence_condition_blocks_authorization(self):
        self.test_conditionally_ready_without_authority()
        self.d['slices'][0]['conditions'][0]['high_consequence']=True
        authorize(self.m,self.d)
        self.fails('high-consequence')

    def test_invalid_input_may_be_empty(self):
        self.m['readiness']='invalid_input'
        self.d={k:[] for k in self.d}
        self.assertEqual(self.run_check(),[])

    def test_ready_empty_is_rejected(self):
        self.d={k:[] for k in self.d}
        self.fails('nonempty')

    def test_observed_source_separate_and_excluded_not_used(self):
        self.m['sources'][0]['kind']='observed'
        self.m['source_policy'].update(authoritative_sources=[],excluded_sources=['SRC-001'])
        self.fails('excluded source')

    def test_observed_fact_does_not_authorize_desired_behavior(self):
        self.m['sources'][0]['kind']='observed'
        self.fails('authoritative normative source')

    def test_approval_does_not_override_material_blocker(self):
        authorize(self.m,self.d)
        self.d['slices'][0]['blockers']=['关键语义未知']
        self.fails('cannot have blockers')

    def test_superseded_does_not_authorize(self):
        authorize(self.m,self.d)
        self.m['baseline_status']='superseded'
        self.fails('superseded')

    def test_valid_conditional_authorization(self):
        self.test_conditionally_ready_without_authority()
        authorize(self.m,self.d)
        self.assertEqual(self.run_check(),[])

    def test_cross_slice_condition_isolation_rejected(self):
        self.test_conditionally_ready_without_authority()
        self.second_slice()
        self.d['slices'][0]['conditions'][0]['invalidated_tasks']=['DEV-2']
        self.fails('isolation spans')

    def test_duplicate_id_rejected(self):
        self.d['requirements'].append(copy.deepcopy(self.d['requirements'][0]))
        self.fails('array items are not unique')

    def test_html_tamper_without_source_change_rejected(self):
        self.assertEqual(self.run_check(),[])
        path=self.p/'development-ready.html'
        path.write_text(path.read_text(encoding='utf-8').replace('<main>','<main><p>错误结论</p>'), encoding='utf-8')
        self.assertTrue(any('body differs' in e for e in validate_package(str(self.root),self.m['package_path'])))

    def test_document_shell_tamper_is_rejected(self):
        self.assertEqual(self.run_check(), [])
        for tag in ['<script>/* inert */</script>', '<base href="https://example.invalid/">',
                    '<style>main { display:none }</style>']:
            path=self.p/'development-ready.html'
            materialize(self.p,self.m,self.c,self.d)
            path.write_text(path.read_text(encoding='utf-8').replace('</head>',tag+'</head>'),encoding='utf-8')
            self.assertTrue(any('shell differs' in e for e in validate_package(str(self.root),self.m['package_path'])))

    def test_custom_readable_title_is_recorded_in_manifest(self):
        self.m['readable_title']='评审阅读版'
        self.assertEqual(self.run_check(), [])
        self.assertIn('<title>评审阅读版</title>',(self.p/'development-ready.html').read_text(encoding='utf-8'))
        with self.assertRaises(ValueError):
            build_html(self.p/'development-ready.md',(self.p/'development-ready.md').read_text(encoding='utf-8'),'未登记标题')

    def diagram_fixture(self, markdown):
        self.m.update(complex_relationships=True,diagrams=[{'source':'graph.mmd','image':'graph.svg','evidence':'合成图核对'}])
        self.m['artifacts']+=['graph.mmd','graph.svg']
        (self.p/'graph.mmd').write_text('flowchart LR\n A --> B',encoding='utf-8')
        (self.p/'graph.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"><title>图</title></svg>',encoding='utf-8')
        materialize(self.p,self.m,self.c,self.d,markdown)
        return validate_package(str(self.root),self.m['package_path'])

    def test_inline_diagram_really_renders(self):
        self.assertEqual(self.diagram_fixture('\n关系如下：![关系图](graph.svg)\n'), [])
        self.assertIn('<a href="graph.svg"><img src="graph.svg"',(self.p/'development-ready.html').read_text(encoding='utf-8'))

    def test_context_version_must_match_manifest(self):
        self.c['framework_version']='0.10.0-candidate.1'
        self.fails('context framework_version must match')

    def test_diagram_reference_inside_code_is_not_visible_diagram(self):
        errors=self.diagram_fixture('\n```text\n![关系图](graph.svg)\n```\n')
        self.assertTrue(any('not rendered as an image' in e for e in errors),errors)

    def test_prior_current_format_remains_supported(self):
        self.m['framework_version']='0.10.0-candidate.1'
        self.c['framework_version']='0.10.0-candidate.1'
        self.assertEqual(self.run_check(), [])

    def test_windows_legacy_format_reports_explicit_migration_boundary(self):
        self.assertEqual(self.run_check(), [])
        self.m['framework_version']='0.9.0-candidate.5'
        write_json(self.p/'package-manifest.json',self.m)
        with patch('validate_project_package.sys.platform','win32'):
            errors=validate_package(str(self.root),self.m['package_path'])
        self.assertTrue(any('requires POSIX project_root' in error and 'migrate explicitly' in error for error in errors),errors)

    def test_manifest_symlink_escape(self):
        self.assertEqual(self.run_check(),[])
        path=self.p/'package-manifest.json'
        outside=Path(self.holder.name)/'manifest.json'
        path.rename(outside)
        try:
            path.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest('host does not permit symbolic links')
        self.assertIn('manifest escapes',validate_package(str(self.root),self.m['package_path'])[0])

    def test_renderer_contains_task_details_and_navigation(self):
        self.assertEqual(self.run_check(),[])
        text=(self.p/'development-ready.html').read_text(encoding='utf-8')
        self.assertIn('href="#structured-plan"',text)
        self.assertIn('DEV-1 导出本地任务列表',text)
        self.assertIn('已确认职责',text)
        self.assertIn('不访问网络',text)

    def test_role_overlap(self):
        self.m['source_policy']['supporting_sources']=['SRC-001']
        self.fails('mutually exclusive')

    def test_invalid_source_date(self):
        self.m['sources'][0]['checked_at']='昨天'
        self.fails('ISO date')

    def test_delta_requires_baseline(self):
        self.m['mode']='delta'
        self.fails('baseline_refs')

    def test_delta_with_change_ledger(self):
        self.m.update(mode='delta',route='light',baseline_refs=[{'package_id':'REQ-OLD','version':'1.0',
                       'locator':'历史基线（合成引用）','reused_items':['REQ-F1']}])
        self.d['changes']=[{'kind':'changed','id':'REQ-F1','before':'空列表不生成文件',
                           'after':'空列表生成仅表头 CSV','affected_tasks':['DEV-1']}]
        self.assertEqual(self.run_check(),[])

    def test_stale_markdown(self):
        self.assertEqual(self.run_check(),[])
        with (self.p/'development-ready.md').open('a') as f: f.write('\n新规则\n')
        self.assertTrue(any('stale' in e for e in validate_package(str(self.root),self.m['package_path'])))

    def test_stale_plan(self):
        self.assertEqual(self.run_check(),[])
        self.d['tasks'][0]['title']='更改任务语义'
        write_json(self.p/'delivery-plan.json',self.d)
        self.assertTrue(any('stale' in e for e in validate_package(str(self.root),self.m['package_path'])))

    def test_visible_diagram_and_freshness(self):
        self.m.update(complex_relationships=True,diagrams=[{'source':'graph.mmd','image':'graph.svg',
                                                            'evidence':'合成图人工核对说明'}])
        self.m['artifacts']+=['graph.mmd','graph.svg']
        (self.p/'graph.mmd').write_text('flowchart LR\n A --> B', encoding='utf-8')
        (self.p/'graph.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"><text>A → B</text></svg>', encoding='utf-8')
        materialize(self.p,self.m,self.c,self.d,'\n![关系图](graph.svg)\n')
        self.assertEqual(validate_package(str(self.root),self.m['package_path']),[])
        (self.p/'graph.svg').write_text('<svg/>', encoding='utf-8')
        self.assertTrue(any('stale' in e for e in validate_package(str(self.root),self.m['package_path'])))

    def test_complex_relationships_need_diagram(self):
        self.m['complex_relationships']=True
        self.fails('require visible diagrams')

    def test_readable_waiver_requires_evidence(self):
        self.m['readable_artifact']=''
        self.m['artifacts'].remove('development-ready.html')
        self.fails('requires readable HTML')
        self.m['readable_waiver']={'tool':'项目原有文档工具','evidence':'合成阅览核对记录','owner':'M1'}
        self.assertEqual(self.run_check(),[])

    def test_multiple_packages_share_entrypoint(self):
        self.assertEqual(self.run_check(),[])
        p,m,c,d = sample(self.root,'REQ-002')
        materialize(p,m,c,d)
        self.assertEqual(validate_package(str(self.root),m['package_path']),[])
        self.assertEqual(validate_package(str(self.root),self.m['package_path']),[])

    def test_relocated_project(self):
        self.assertEqual(self.run_check(),[])
        new_root = Path(self.holder.name)/'renamed-project'
        shutil.copytree(self.root,new_root)
        self.assertEqual(validate_package(str(new_root),self.m['package_path']),[])

    def test_wrong_entrypoint_rejected(self):
        self.assertEqual(self.run_check(),[])
        (self.root/'docs/pre-development/index.md').write_text('[错误](wrong/development-ready.md)', encoding='utf-8')
        self.assertTrue(any('must link this package' in e for e in validate_package(str(self.root),self.m['package_path'])))

    def test_windows_absolute_artifact_rejected(self):
        self.assertEqual(self.run_check(),[])
        self.m['artifacts'].append('C:\\private\\secret.md')
        write_json(self.p/'package-manifest.json',self.m)
        self.assertTrue(any('unsafe relative path' in e for e in validate_package(str(self.root),self.m['package_path'])))

    def test_symlink_artifact_escape(self):
        self.assertEqual(self.run_check(),[])
        outside = Path(self.holder.name)/'outside.md'; outside.write_text('outside', encoding='utf-8')
        try:
            (self.p/'escape.md').symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest('host does not permit symbolic links')
        self.m['artifacts'].append('escape.md');write_json(self.p/'package-manifest.json',self.m)
        self.assertTrue(any('escapes directory' in e for e in validate_package(str(self.root),self.m['package_path'])))

    def test_unknown_version_rejected(self):
        self.assertEqual(self.run_check(),[])
        self.m['framework_version']='1.0.0';write_json(self.p/'package-manifest.json',self.m)
        self.assertIn('unsupported framework_version',validate_package(str(self.root),self.m['package_path'])[0])

    def test_malformed_shape_returns_errors(self):
        self.assertEqual(self.run_check(),[])
        write_json(self.p/'delivery-plan.json',{'tasks':False})
        self.assertTrue(validate_package(str(self.root),self.m['package_path']))

    def test_markdown_escaped_and_code_pipes(self):
        self.assertEqual(split_table_row(r'| a\|b | `c|d` |'),['a|b','`c|d`'])

    def test_active_link_scheme_not_rendered(self):
        self.assertNotIn('href="javascript:',render_inline('[点击](javascript:alert)'))


if __name__ == '__main__': unittest.main()
