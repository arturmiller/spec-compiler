from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


def node(script):
    result = subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT,
                            encoding='utf-8', capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(not shutil.which('node'), reason='Renderer requires Node')
def test_explanations_wrap_escape_and_reject_insufficient_node_height():
    node("""
import assert from 'node:assert/strict';
import { summaryLines, renderSummary } from './tools/vendor/archify/renderers/shared/node-explanation.mjs';
import { focusNodeAttrs } from './tools/vendor/archify/renderers/shared/cli.mjs';
assert.deepEqual(summaryLines('One two three four five six', 100), ['One two three', 'four five six']);
assert.throws(()=>renderSummary({id:'short',summary:'One two three four five six'},50,0,100,70), /more height/);
assert.throws(()=>summaryLines('unbreakableverylongword',40), /too wide/);
const summary=renderSummary({id:'safe',summary:'<script> & text'},100,0,200,124);
assert(!summary.includes('<script>'));
assert(summary.includes('&lt;script&gt;') && summary.includes('&amp;'));
const attrs=focusNodeAttrs('safe','Safe',{description:'\" onload=\"alert(1) <script>',links:[{label:'\" unsafe',href:'../reference/glossary.html#spec'}]});
assert(attrs.includes('&quot;') && !attrs.includes('<script>'));
""")


@pytest.mark.skipif(not shutil.which('node'), reason='Renderer requires Node')
@pytest.mark.parametrize('kind,collection', [('architecture','components'), ('sequence','participants'), ('lifecycle','states')])
def test_explanation_schema_accepts_local_links_and_rejects_active_urls(kind, collection):
    name = {'architecture':'compiler-components','sequence':'compile-contracts','lifecycle':'decision-lifecycle'}[kind]
    node(f"""
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {{validateSchema}} from './tools/vendor/archify/renderers/shared/validator.mjs';
const model=JSON.parse(fs.readFileSync('./docs/diagrams/{name}.json','utf8'));
validateSchema('{kind}',model);
for(const href of ['javascript:alert(1)','https://example.org','//example.org','data:text/html,x']) {{
  model.{collection}[0].links=[{{label:'Unsafe',href}}];
  assert.throws(()=>validateSchema('{kind}',model));
}}
""")


def test_diagram_links_require_a_published_route_and_existing_anchor(tmp_path, monkeypatch):
    from tools import documentation_site as site
    monkeypatch.setattr(site, 'ROOT', tmp_path)
    monkeypatch.setattr(site, 'SOURCES', tmp_path / 'docs')
    (tmp_path / 'docs/diagrams').mkdir(parents=True)
    (tmp_path / 'docs/index.html').write_text('<html><head><meta name="doc-route" content=""><title>Test</title></head><body><main><h1 id="target">Test</h1></main></body></html>')
    diagram = tmp_path / 'docs/diagrams/test.json'
    model = {'diagram_type':'architecture','meta':{'quality_profile':'showcase'},
             'components':[{'id':'node','links':[{'label':'Explanation','href':'../#target'}]}]}
    diagram.write_text(json.dumps(model))
    site.validate_sources(render_diagrams=False)
    model['components'][0]['links'][0]['href']='../#missing'
    diagram.write_text(json.dumps(model))
    with pytest.raises(ValueError, match='Missing diagram documentation anchor'):
        site.validate_sources(render_diagrams=False)
    model['components'][0]['links'][0]['href']='../unpublished.html'
    diagram.write_text(json.dumps(model))
    with pytest.raises(ValueError, match='Invalid diagram documentation link'):
        site.validate_sources(render_diagrams=False)
