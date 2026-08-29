from pathlib import Path

from rdflib import Graph
import pytest

from tools.generate import read_compiler_contract


def _graph(
    contract_type: str = "ex:TransformationContract",
    product_type: str = "schema:SoftwareApplication",
) -> Graph:
    graph = Graph()
    graph.parse(
        data=f'''@prefix ex: <https://example.org/catalog/> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix schema: <https://schema.org/> .

ex:ReplaceableImplementation a {product_type} ;
    dcterms:conformsTo ex:CompilerProtocolV1 ;
    ex:implementsContract ex:CompilationV1 .

ex:CompilationV1 a {contract_type} ;
    ex:inputSpecPattern "specs/*.ttl" ;
    ex:validFixtureProduct "fixture" ;
    ex:generatesArtifact "generated/result.txt" ;
    ex:rejectsMissingSpecs true ;
    ex:deterministicOutput true .
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


def test_compiler_protocol_requires_a_transformation_contract(tmp_path: Path):
    (tmp_path / "fixture").mkdir()

    with pytest.raises(ValueError, match="ex:TransformationContract"):
        read_compiler_contract(tmp_path, _graph("ex:UnrelatedContract"))


def test_protocol_dispatch_does_not_replace_general_product_type(tmp_path: Path):
    (tmp_path / "fixture").mkdir()

    with pytest.raises(ValueError, match="schema:SoftwareApplication"):
        read_compiler_contract(
            tmp_path,
            _graph(product_type="ex:ContractCompiler"),
        )
