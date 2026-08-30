from pathlib import Path

from rdflib import Graph
import pytest

from tools.generate import read_compiler_contract


def _graph(
    contract_type: str = "sco:TransformationContract",
    product_type: str = "schema:SoftwareApplication",
    bootstrap: str = "",
) -> Graph:
    graph = Graph()
    graph.parse(
        data=f'''@prefix sco: <https://arturmiller.github.io/spec-compiler/ontology/#> .
@prefix resource: <https://arturmiller.github.io/spec-compiler/resources/test/#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix schema: <https://schema.org/> .

resource:ReplaceableImplementation a {product_type} ;
    dcterms:conformsTo sco:CompilerProtocolV1 ;
    sco:implementsContract resource:CompilationV1 .

resource:CompilationV1 a {contract_type} ;
    sco:inputSpecPattern "specs/*.ttl" ;
    sco:validFixtureProduct "fixture" ;
    sco:generatesArtifact "generated/result.txt" ;
    sco:rejectsMissingSpecs true ;
    sco:deterministicOutput true .

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
    assert contract["bootstrap"] is None


def test_bootstrap_provenance_keeps_seed_separate_from_product_contract(
    tmp_path: Path,
):
    (tmp_path / "fixture").mkdir()
    bootstrap = """
resource:SeedG0 a schema:SoftwareApplication .
resource:BootstrapV1 a sco:BootstrapProcess ;
    sco:bootstrapsProduct resource:ReplaceableImplementation ;
    sco:seedImplementation resource:SeedG0 ;
    sco:evolutionStrategy sco:ModifyExistingImplementation ;
    sco:generatesImplementationArtifact "src/spec_compiler.py" .
"""

    contract = read_compiler_contract(
        tmp_path,
        _graph(bootstrap=bootstrap),
    )

    assert contract["bootstrap"] == {
        "process": "https://arturmiller.github.io/spec-compiler/resources/test/#BootstrapV1",
        "seed_implementation": "https://arturmiller.github.io/spec-compiler/resources/test/#SeedG0",
        "evolution_strategy": "https://arturmiller.github.io/spec-compiler/ontology/#ModifyExistingImplementation",
        "implementation_artifact": "src/spec_compiler.py",
        "implementation_generation": 1,
    }


def test_bootstrap_seed_must_be_a_software_application(tmp_path: Path):
    (tmp_path / "fixture").mkdir()
    bootstrap = """
resource:BootstrapV1 a sco:BootstrapProcess ;
    sco:bootstrapsProduct resource:ReplaceableImplementation ;
    sco:seedImplementation resource:SeedG0 ;
    sco:evolutionStrategy sco:ModifyExistingImplementation ;
    sco:generatesImplementationArtifact "src/spec_compiler.py" .
"""

    with pytest.raises(ValueError, match="Bootstrap seed"):
        read_compiler_contract(tmp_path, _graph(bootstrap=bootstrap))


def test_bootstrap_implementation_artifact_must_stay_in_bundle(tmp_path: Path):
    (tmp_path / "fixture").mkdir()
    bootstrap = """
resource:SeedG0 a schema:SoftwareApplication .
resource:BootstrapV1 a sco:BootstrapProcess ;
    sco:bootstrapsProduct resource:ReplaceableImplementation ;
    sco:seedImplementation resource:SeedG0 ;
    sco:evolutionStrategy sco:ModifyExistingImplementation ;
    sco:generatesImplementationArtifact "../outside.py" .
"""

    with pytest.raises(ValueError, match="must stay in the input bundle"):
        read_compiler_contract(tmp_path, _graph(bootstrap=bootstrap))


def test_compiler_protocol_requires_a_transformation_contract(tmp_path: Path):
    (tmp_path / "fixture").mkdir()

    with pytest.raises(ValueError, match="sco:TransformationContract"):
        read_compiler_contract(tmp_path, _graph("sco:UnrelatedContract"))


def test_protocol_dispatch_does_not_replace_general_product_type(tmp_path: Path):
    (tmp_path / "fixture").mkdir()

    with pytest.raises(ValueError, match="schema:SoftwareApplication"):
        read_compiler_contract(
            tmp_path,
            _graph(product_type="sco:ContractCompiler"),
        )
