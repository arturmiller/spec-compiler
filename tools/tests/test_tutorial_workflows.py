"""Execute the published tutorial changes against isolated, real products."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from tools import tutorial_workspace as tutorial

ROOT = Path(__file__).resolve().parents[2]


def authored_snapshot(directory):
    return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.rglob('*') if p.is_file() and '.venv' not in p.parts
            and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts}


def run(*arguments, cwd=ROOT, input=None):
    return subprocess.run([sys.executable, *map(str, arguments)], cwd=cwd, input=input,
                          encoding='utf-8', capture_output=True, timeout=180,
                          env={**os.environ, 'PYTHONUTF8': '1'})


def generate(product):
    result = run(ROOT / 'tools/generate.py', '--product', product)
    assert result.returncode == 0, result.stdout + result.stderr


def prove(product):
    result = run('-m', 'pytest', '-q', product / 'tests')
    assert result.returncode == 0, result.stdout + result.stderr
    return result


@pytest.mark.parametrize('example', ['sql-api', 'kfw', 'cloud'])
def test_tutorial_spec_change_and_real_product_effect(tmp_path, example):
    reference = ROOT / 'products' / tutorial.EXAMPLES[example]
    before = authored_snapshot(reference)
    source = tmp_path / 'products' / reference.name
    shutil.copytree(reference, source, ignore=shutil.ignore_patterns(
        '.venv', '__pycache__', '.pytest_cache', '*.sqlite3', '.cache'))
    product = tutorial.create(example, tmp_path)
    generate(product)
    prove(product)

    if example == 'sql-api':
        spec = product / 'specs/article_shape.ttl'
        text = spec.read_text(encoding='utf-8')
        assert text.count('sh:minLength 1') == 1
        spec.write_text(text.replace('sh:minLength 1', 'sh:minLength 3'), encoding='utf-8')
        generate(product)
        contract = json.loads((product / 'generated/expected-openapi.json').read_text())
        response = contract['paths']['/articles/{id}']['get']['responses']['200']
        assert response['content']['application/json']['schema']['properties']['description']['minLength'] == 3
        assert "'description': 'xxx'" in (product / 'tests/test_contract.py').read_text()
        failure = run('-m', 'pytest', '-q', product / 'tests')
        assert failure.returncode == 1, failure.stdout + failure.stderr
        assert 'test_openapi' in failure.stdout and 'minLength' in failure.stdout
        implementation = product / 'app.py'
        implementation.write_text(implementation.read_text().replace('Field(min_length=1)', 'Field(min_length=3)'), encoding='utf-8')
    elif example == 'kfw':
        request = (product / 'examples/eligible-request.json').read_text(encoding='utf-8')
        actual = subprocess.run(['uv', 'run', '--locked', 'python', 'app.py', '--contract', './generated/decision-contract.json'],
                                cwd=product, input=request, encoding='utf-8', capture_output=True, timeout=180,
                                env={**os.environ, 'PYTHONUTF8': '1'})
        assert actual.returncode == 0, actual.stdout + actual.stderr
        result = json.loads(actual.stdout)
        assert result['outcome'] == 'eligible' and result['rule_set_version_label'] == '2026-07'
        spec = product / 'specs/http_api.ttl'
        text = spec.read_text(encoding='utf-8')
        assert text.count('sco:statusCode 200') == 1
        spec.write_text(text.replace('sco:statusCode 200', 'sco:statusCode 202'), encoding='utf-8')
        generate(product)
        contract = json.loads((product / 'generated/expected-openapi.json').read_text())
        assert '202' in contract['paths']['/eligibility-decisions']['post']['responses']
    else:
        spec = product / 'specs/decision_contract.ttl'
        text = spec.read_text(encoding='utf-8')
        old = 'Does access to privileged accounts use multi-factor authentication?'
        new = 'Nutzen privilegierte Konten Multi-Faktor-Authentifizierung?'
        assert text.count(old) == 1
        spec.write_text(text.replace(old, new), encoding='utf-8')
        generate(product)
        assert new in (product / 'generated/decision-contract.json').read_text(encoding='utf-8')
    prove(product)
    assert authored_snapshot(reference) == before
