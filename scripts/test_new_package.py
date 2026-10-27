"""Exercise the public entry point with temporary projects, never real projects."""
import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from new_package import prepare
from validate_project_package import validate_package

FRAMEWORK = Path(__file__).resolve().parents[1]


class NewPackageTests(unittest.TestCase):
    def setUp(self):
        self.holder=tempfile.TemporaryDirectory()
        self.addCleanup(self.holder.cleanup)
        self.root=Path(self.holder.name)/'project with space'
        self.root.mkdir()
        self.brief=Path(self.holder.name)/'brief.json'
        self.data=json.loads((FRAMEWORK/'templates/quick-input.json').read_text(encoding='utf-8'))
        self.write_brief()

    def write_brief(self):
        self.brief.write_text(json.dumps(self.data,ensure_ascii=False),encoding='utf-8')

    def cli(self,*args):
        return subprocess.run([sys.executable,'-B',str(FRAMEWORK/'scripts/new_package.py'),
                               '--project-root',str(self.root),'--brief',str(self.brief),*args],
                              capture_output=True,text=True,encoding='utf-8')

    def test_create_then_validate_without_fabricated_authority(self):
        result=self.cli()
        self.assertEqual(result.returncode,0,result.stderr)
        package=self.root/'docs/pre-development/REQ-001-local-export'
        self.assertEqual(validate_package(str(self.root),str(package)),[])
        manifest=json.loads((package/'package-manifest.json').read_text(encoding='utf-8'))
        self.assertEqual((manifest['baseline_status'],manifest['readiness'],manifest['development_scope']),
                         ('candidate','not_assessed','none'))
        context=json.loads((package/'project-context.json').read_text(encoding='utf-8'))
        self.assertEqual(context['team'],[])
        self.assertEqual(manifest['authorized_work'],[])
        self.assertEqual((package/'input-brief.json').read_bytes(),self.brief.read_bytes())
        relocated=Path(self.holder.name)/'relocated'
        shutil.copytree(self.root,relocated)
        self.assertEqual(validate_package(str(relocated),manifest['package_path']),[])

    def test_dry_run_writes_nothing(self):
        result=self.cli('--dry-run')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(list(self.root.iterdir()),[])

    def test_existing_package_is_not_overwritten(self):
        self.assertEqual(self.cli().returncode,0)
        before={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertNotEqual(self.cli().returncode,0)
        self.assertEqual(before,{p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_existing_index_and_readme_are_preserved(self):
        readme=self.root/'README.md';readme.write_text('Existing project\n',encoding='utf-8')
        index=self.root/'docs/pre-development/index.md';index.parent.mkdir(parents=True)
        index.write_text('# Existing index\n',encoding='utf-8')
        self.assertEqual(self.cli().returncode,0)
        self.assertEqual(readme.read_text(encoding='utf-8'),'Existing project\n')
        self.assertTrue(index.read_text(encoding='utf-8').startswith('# Existing index\n'))

    def test_unknown_owner_fails_before_writing(self):
        self.data['owner']='MISSING';self.write_brief()
        result=self.cli()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('unknown reference',result.stderr)
        self.assertEqual(list(self.root.iterdir()),[])

    def test_team_input_is_not_silently_confirmed(self):
        self.data.update(owner='M1',team=[dict(member_id='M1',confirmed_responsibilities=[],availability='待确认',capabilities=[])])
        self.write_brief()
        self.assertEqual(self.cli().returncode,0)
        context=json.loads((self.root/'docs/pre-development/REQ-001-local-export/project-context.json').read_text(encoding='utf-8'))
        self.assertEqual(context['team'][0]['confirmed_responsibilities'],[])

    def test_unsafe_identifiers_fail_before_writing(self):
        for key,value in [('package_slug','../../escape'),('package_id','../REQ-001'),('package_slug','C:\\escape')]:
            original=copy.deepcopy(self.data);self.data[key]=value;self.write_brief()
            self.assertNotEqual(self.cli().returncode,0)
            self.assertEqual(list(self.root.iterdir()),[])
            self.data=original

    def test_invalid_team_shape_fails_before_writing(self):
        self.data['team']=[{'member_id':'M1'}];self.write_brief()
        self.assertNotEqual(self.cli().returncode,0)
        self.assertEqual(list(self.root.iterdir()),[])

    def test_input_cannot_be_output_index(self):
        self.brief=self.root/'docs/pre-development/index.md'
        self.brief.parent.mkdir(parents=True);self.write_brief()
        before=self.brief.read_bytes()
        with self.assertRaisesRegex(ValueError,'output index'):
            prepare(str(self.root),str(self.brief))
        self.assertEqual(self.brief.read_bytes(),before)

    def test_symlink_escape_is_rejected(self):
        target=Path(self.holder.name)/'outside';target.mkdir()
        try:
            (self.root/'docs').symlink_to(target,target_is_directory=True)
        except (OSError,NotImplementedError):
            self.skipTest('host does not permit symbolic links')
        result=self.cli()
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(list(target.iterdir()),[])

    def test_missing_project_is_not_created(self):
        self.root=self.root/'missing'
        self.assertNotEqual(self.cli().returncode,0)
        self.assertFalse(self.root.exists())


if __name__ == '__main__':
    unittest.main()
