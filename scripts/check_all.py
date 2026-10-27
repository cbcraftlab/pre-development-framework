#!/usr/bin/env python3
"""Run offline repository, regression and checked-in example gates."""
from pathlib import Path
import subprocess
import sys

from validate_project_package import validate_package

ROOT = Path(__file__).resolve().parents[1]


def main():
    for args in [('scripts/validate_repository.py',),('-m','unittest','discover','-s','scripts','-p','test_*.py')]:
        result=subprocess.run([sys.executable,'-B',*args],cwd=str(ROOT))
        if result.returncode:
            return result.returncode
    examples=ROOT/'examples/synthetic-project'
    packages=sorted(examples.rglob('package-manifest.json'))
    if not packages:
        print('EXAMPLE VALIDATION FAILED: no example packages')
        return 1
    for manifest in packages:
        errors=validate_package(str(examples),str(manifest.parent))
        if errors:
            print(f'EXAMPLE VALIDATION FAILED: {manifest.parent.name}')
            for error in errors:
                print('- '+error)
            return 1
        print(f'EXAMPLE PASSED: {manifest.parent.name}')
    print('ALL LOCAL GATES PASSED; model behavior, real-project effectiveness and hosted CI are separate evidence.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
