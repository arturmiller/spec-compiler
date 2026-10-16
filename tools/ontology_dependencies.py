"""Derive the validated local ontology DAG, including optional terminal product specs."""
from __future__ import annotations

from copy import deepcopy
import html
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, OWL

if __package__:
    from .ontology_reference import canonical_graph
    from .generate import ontology_module, validate_ontology_modules
else:
    from ontology_reference import canonical_graph
    from generate import ontology_module, validate_ontology_modules

PROJECT_ONTOLOGY_ROOT = 'https://arturmiller.github.io/spec-compiler/ontology/'


def _title(graph, ontology, language):
    values = sorted(str(value) for value in graph.objects(ontology, DCTERMS.title)
                    if value.language == language)
    if len(values) != 1:
        raise ValueError(f'Ontology {ontology} needs exactly one {language} title')
    return values[0]


def read_dependencies(publications, product_roots=()) -> dict:
    """A -> B means A imports B or uses a named term defined in B.

    Every project-term use requires an explicit import. Products are terminal
    users, never import targets. Namespace declarations, literals, fixture paths
    and runtime calls are not ontology dependencies. No remote resolution.
    """
    nodes, graphs, modules = [], {}, []
    for source, iri, namespace in publications:
        graph = canonical_graph(Graph().parse(source, format='turtle'))
        key = iri.rstrip('/').rsplit('/', 1)[-1]
        key = 'contract' if key == 'ontology' else key
        ontology = URIRef(iri)
        nodes.append({'key': key, 'iri': iri, 'namespace': namespace,
                      'role': 'reusable',
                      'title': _title(graph, ontology, 'en'),
                      'titleDe': _title(graph, ontology, 'de'),
                      'source': Path(source).name})
        if key in graphs:
            raise ValueError(f'Duplicate ontology identity: {key}')
        graphs[key] = graph
        modules.append({'graph': graph, 'iri': iri, 'namespace': namespace,
                        'role': 'reusable', 'source': str(source)})
    for root in sorted(product_roots):
        graph = Graph()
        for source in sorted((root / 'specs').glob('*.ttl')):
            graph.parse(source, format='turtle')
        graph = canonical_graph(graph)
        module = ontology_module(graph, role='product', source=str(root / 'specs'))
        key = 'product-' + root.name
        iri, namespace = module['iri'], module['namespace']
        nodes.append({'key': key, 'iri': iri, 'namespace': namespace,
                      'role': 'product', 'product': root.name,
                      'title': _title(graph, URIRef(iri), 'en'),
                      'titleDe': _title(graph, URIRef(iri), 'de'),
                      'source': root.name + '/specs/*.ttl'})
        graphs[key] = graph
        modules.append(module)
    validate_ontology_modules(modules)
    nodes.sort(key=lambda node: node['key'])
    by_iri = {node['iri']: node for node in nodes}
    dependencies = []
    for node in nodes:
        graph = graphs[node['key']]
        imports = set(str(value) for value in graph.objects(URIRef(node['iri']), OWL.imports))
        if node['iri'] in imports:
            raise ValueError(f'Ontology cannot import itself: {node["iri"]}')
        unknown = {iri for iri in imports if iri.startswith(PROJECT_ONTOLOGY_ROOT) and iri not in by_iri}
        if unknown:
            raise ValueError(f'Unknown project ontology import: {sorted(unknown)}')
        terms, evidence = {}, {}
        for triple in graph:
            for value in triple:
                if not isinstance(value, URIRef):
                    continue
                owner = next((candidate for candidate in nodes
                              if str(value).startswith(candidate['namespace'])), None)
                if owner is None:
                    if str(value).startswith(PROJECT_ONTOLOGY_ROOT) and '#' in str(value):
                        raise ValueError(f'Unknown project ontology term: {value}')
                    continue
                if owner['key'] == node['key']:
                    continue
                terms.setdefault(owner['key'], set()).add(str(value))
                evidence.setdefault(owner['key'], set()).add(tuple(str(term) for term in triple))
        for target in nodes:
            if target['key'] == node['key']:
                continue
            imported = target['iri'] in imports
            references = sorted(terms.get(target['key'], set()))
            if imported or references:
                statements = set(evidence.get(target['key'], set()))
                if imported:
                    statements.add((node['iri'], str(OWL.imports), target['iri']))
                dependencies.append({'from': node['key'], 'to': target['key'],
                                     'imports': imported, 'terms': references,
                                     'statements': [list(row) for row in sorted(statements)]})
    direct = {node['key']: set() for node in nodes}
    for edge in dependencies:
        direct[edge['from']].add(edge['to'])
    transitive = {}
    for key in direct:
        reached, pending = set(), list(direct[key])
        while pending:
            target = pending.pop()
            if target in reached:
                continue
            reached.add(target)
            pending.extend(direct[target] - reached)
        transitive[key] = sorted(reached - {key})
    return {'schemaVersion': 2, 'scope': 'project-ontology-modules',
            'direction': 'dependent-to-required', 'nodes': nodes,
            'dependencies': dependencies, 'transitive': transitive,
            'noProjectDependencies': sorted(key for key, targets in transitive.items() if not targets)}


def dependency_diagram(layout: dict, analysis: dict) -> dict:
    """JSON owns presentation; RDF owns identities and all directed relationships.

    Existing connection records only supply diagnosed geometry controls by ID;
    their from/to/label fields never create an ontology dependency.
    """
    model = deepcopy(layout)
    actual = {node['key']: node for node in analysis['nodes']}
    components = model['components']
    if len(components) != len(actual) or {node['id'] for node in components} != set(actual):
        raise ValueError('Dependency diagram must contain exactly the published project ontologies')
    for node in components:
        if node['label'] != actual[node['id']]['title']:
            raise ValueError(f'Ontology diagram title is stale: {node["id"]}')
    controls = {edge['id']: edge for edge in model.get('connections', [])}
    geometry = ('labelDx', 'labelDy', 'labelAt', 'labelSegment', 'fromSide', 'toSide', 'via', 'route', 'width')
    connections = []
    for edge in analysis['dependencies']:
        identifier = edge['from'] + '-to-' + edge['to']
        label = 'importiert'
        connection = {'id': identifier, 'from': edge['from'], 'to': edge['to'],
                      'label': label, 'variant': 'emphasis'}
        connection.update({key: controls[identifier][key] for key in geometry
                           if identifier in controls and key in controls[identifier]})
        connections.append(connection)
    model['connections'] = connections
    return model


def dependency_tables(analysis: dict) -> str:
    """Accessible relationship evidence and complete directional dependency matrix."""
    nodes = analysis['nodes']
    by_key = {node['key']: node for node in nodes}
    direct = {(edge['from'], edge['to']) for edge in analysis['dependencies']}
    names = {'contract': 'HTTP', 'sql': 'SQL', 'decision-protocol': 'Decision-Protokoll',
             'decision': 'Decision', 'compiler': 'Compiler',
             'funding': 'Förderung', 'cloud': 'Cloud'}
    esc = html.escape
    def caption(key):
        return names.get(key, by_key[key]['titleDe'])
    def graph_link(key):
        return f'<a href="./?ontology={esc(key, quote=True)}">{esc(caption(key))}</a>'
    rows = []
    for edge in analysis['dependencies']:
        source, target = by_key[edge['from']], by_key[edge['to']]
        statements = []
        source_route = '../ontology/' + (source['key'] + '/' if source['key'] != 'contract' else '')
        for subject, predicate, value in edge['statements']:
            anchor = subject[len(source['namespace']):] if subject.startswith(source['namespace']) else 'overview'
            statements.append(f'<li><a href="{source_route}index-de.html#{esc(anchor, quote=True)}">'
                              f'{esc(subject.rsplit("#", 1)[-1])}</a> · '
                              f'{esc(predicate.rsplit("#", 1)[-1])} → '
                              f'<code>{esc(value)}</code></li>')
        explanation = ('Expliziter OWL-Import und Begriffsverwendung' if edge['imports'] and edge['terms'] else
                       'Expliziter OWL-Import' if edge['imports'] else 'Begriffsverwendung ohne OWL-Import')
        rows.append(f'<tr data-dependency-from="{esc(source["key"])}" data-dependency-to="{esc(target["key"])}">'
                    f'<td>{graph_link(source["key"])}</td><td>→ {graph_link(target["key"])}</td>'
                    f'<td>{esc(explanation)}<details><summary>RDF-Belege ({len(edge["statements"])})</summary>'
                    f'<ul>{"".join(statements)}</ul></details></td></tr>')
    matrix_rows = []
    for source in nodes:
        cells = []
        for target in nodes:
            relation = ('self' if source['key'] == target['key'] else
                        'direct' if (source['key'], target['key']) in direct else
                        'indirect' if target['key'] in analysis['transitive'][source['key']] else 'none')
            text = {'self': '—', 'direct': 'direkt', 'indirect': 'indirekt', 'none': 'keine'}[relation]
            cells.append(f'<td data-source="{source["key"]}" data-target="{target["key"]}" '
                         f'data-dependency="{relation}">{text}</td>')
        matrix_rows.append(f'<tr><th scope="row">{graph_link(source["key"])}</th>{"".join(cells)}</tr>')
    header = ''.join(f'<th scope="col">{esc(caption(node["key"]))}</th>' for node in nodes)
    independent = ', '.join(caption(key) for key in analysis['noProjectDependencies'])
    return ('<h2 id="direkte-abhaengigkeiten">Direkte Abhängigkeiten und ihre Belege</h2>'
            '<table><thead><tr><th>Nutzende Ontologie</th><th>Benötigte Ontologie</th><th>Grund</th></tr></thead>'
            '<tbody>' + ''.join(rows) + '</tbody></table>'
            '<h2 id="matrix">Welche Richtung besteht – und welche nicht?</h2>'
            '<p>Die <strong>Zeile benötigt die Spalte</strong>. „Keine“ bedeutet weder direkte noch indirekte Abhängigkeit '
            'zwischen diesen Projektontologien. Gemeinsame Nutzung des Decision-Kerns erzeugt keine gegenseitige Abhängigkeit.</p>'
            '<table class="ontology-dependency-matrix"><thead><tr><th>benötigt →</th>' + header + '</tr></thead>'
            '<tbody>' + ''.join(matrix_rows) + '</tbody></table>'
            '<h2 id="unabhaengigkeit">Ohne Abhängigkeit von anderen Projektontologien</h2>'
            '<p>' + esc(independent) + '. Externe Standardvokabulare sind damit nicht ausgeschlossen. '
            'Die Fähigkeit des Compilerwerkzeugs, Produktspecs zu verarbeiten, ist ebenfalls keine Ontologieabhängigkeit.</p>')
