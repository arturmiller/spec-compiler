from pathlib import Path

from rdflib import Graph, Literal, Namespace
from rdflib.namespace import RDF
import pytest

from tools.generate import read_compiler_contract


CCO = Namespace("https://arturmiller.github.io/spec-compiler/ontology/compiler/#")
RESOURCE = Namespace(
    "https://arturmiller.github.io/spec-compiler/resources/test/#"
)


def _graph(
    contract_type: str = "cco:TransformationContract",
    product_type: str = "schema:SoftwareApplication",
    bootstrap: str = "",
) -> Graph:
    graph = Graph()
    graph.parse(
        data=f'''@prefix cco: <https://arturmiller.github.io/spec-compiler/ontology/compiler/#> .
@prefix resource: <https://arturmiller.github.io/spec-compiler/resources/test/#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix schema: <https://schema.org/> .

resource:ReplaceableImplementation a {product_type} ;
    dcterms:conformsTo cco:CompilerProtocolV1 ;
    cco:implementsContract resource:CompilationV1 .

resource:CompilationV1 a {contract_type} ;
    cco:inputSpecPattern "specs/*.ttl" ;
    cco:conformanceFixture resource:Fixture ;
    cco:rejectsMissingSpecs true ;
    cco:deterministicOutput true .

resource:Fixture a cco:CompilerConformanceFixture ;
    cco:fixtureProduct "fixture" ;
    cco:expectsArtifact "generated/result.txt" .

{bootstrap}
''',
        format="turtle",
    )
    return graph


def test_product_identity_is_separate_from_protocol_and_contract(tmp_path: Path):
    (tmp_path / "fixture").mkdir()

    contract = read_compiler_contract(tmp_path, _graph())

    assert contract["name"] == "ReplaceableImplementation"
    assert contract["protocol"].endswith("CompilerProtocolV1")
    assert contract["contract"].endswith("CompilationV1")
    assert contract["conformance_fixtures"] == [
        {
            "name": "Fixture",
            "fixture": (
                "https://arturmiller.github.io/spec-compiler/"
                "resources/test/#Fixture"
            ),
            "product": "fixture",
            "generated_artifacts": ["generated/result.txt"],
        }
    ]
    assert contract["bootstrap"] is None


@pytest.mark.parametrize('term', ['validFixtureProduct', 'generatesArtifact'])
def test_retired_compiler_properties_fail_with_replacement_guidance(tmp_path, term):
    graph = _graph()
    graph.add((RESOURCE.CompilationV1, CCO[term], Literal('ignored-in-the-old-reader')))
    with pytest.raises(ValueError, match='Compiler Vocabulary Retirement v1.*conformanceFixture.*expectsArtifact'):
        read_compiler_contract(tmp_path, graph)


def test_bootstrap_provenance_keeps_seed_separate_from_product_contract(
    tmp_path: Path,
):
    (tmp_path / "fixture").mkdir()
    bootstrap = """
resource:SeedG0 a schema:SoftwareApplication .
resource:BootstrapV1 a cco:BootstrapProcess ;
    cco:bootstrapsProduct resource:ReplaceableImplementation ;
    cco:seedImplementation resource:SeedG0 ;
    cco:evolutionStrategy cco:ModifyExistingImplementation ;
    cco:generatesImplementationArtifact "src/spec_compiler.py" .
"""

    contract = read_compiler_contract(
        tmp_path,
        _graph(bootstrap=bootstrap),
    )

    assert contract["bootstrap"] == {
        "process": "https://arturmiller.github.io/spec-compiler/resources/test/#BootstrapV1",
        "seed_implementation": "https://arturmiller.github.io/spec-compiler/resources/test/#SeedG0",
        "evolution_strategy": "https://arturmiller.github.io/spec-compiler/ontology/compiler/#ModifyExistingImplementation",
        "implementation_artifact": "src/spec_compiler.py",
        "implementation_generation": 1,
    }


def test_bootstrap_seed_must_be_a_software_application(tmp_path: Path):
    (tmp_path / "fixture").mkdir()
    bootstrap = """
resource:BootstrapV1 a cco:BootstrapProcess ;
    cco:bootstrapsProduct resource:ReplaceableImplementation ;
    cco:seedImplementation resource:SeedG0 ;
    cco:evolutionStrategy cco:ModifyExistingImplementation ;
    cco:generatesImplementationArtifact "src/spec_compiler.py" .
"""

    with pytest.raises(ValueError, match="Bootstrap seed"):
        read_compiler_contract(tmp_path, _graph(bootstrap=bootstrap))


def test_bootstrap_implementation_artifact_must_stay_in_bundle(tmp_path: Path):
    (tmp_path / "fixture").mkdir()
    bootstrap = """
resource:SeedG0 a schema:SoftwareApplication .
resource:BootstrapV1 a cco:BootstrapProcess ;
    cco:bootstrapsProduct resource:ReplaceableImplementation ;
    cco:seedImplementation resource:SeedG0 ;
    cco:evolutionStrategy cco:ModifyExistingImplementation ;
    cco:generatesImplementationArtifact "../outside.py" .
"""

    with pytest.raises(ValueError, match="must stay in the input bundle"):
        read_compiler_contract(tmp_path, _graph(bootstrap=bootstrap))


def test_compiler_protocol_requires_a_transformation_contract(tmp_path: Path):
    (tmp_path / "fixture").mkdir()

    with pytest.raises(ValueError, match="cco:TransformationContract"):
        read_compiler_contract(tmp_path, _graph("cco:UnrelatedContract"))


def test_protocol_dispatch_does_not_replace_general_product_type(tmp_path: Path):
    (tmp_path / "fixture").mkdir()

    with pytest.raises(ValueError, match="schema:SoftwareApplication"):
        read_compiler_contract(
            tmp_path,
            _graph(product_type="cco:ContractCompiler"),
        )


def test_every_conformance_fixture_must_be_typed(tmp_path: Path):
    (tmp_path / "fixture").mkdir()
    graph = _graph()
    graph.remove((RESOURCE.Fixture, RDF.type, CCO.CompilerConformanceFixture))

    with pytest.raises(ValueError, match="CompilerConformanceFixture"):
        read_compiler_contract(tmp_path, graph)
