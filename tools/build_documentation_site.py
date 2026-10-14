"""Build the complete static documentation website from HTML and diagram models."""

from __future__ import annotations

import argparse
from pathlib import Path
import tempfile

import build_ontology_site as ontology
import documentation_site as site


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Update HTML, diagrams, and graphs; reuse WIDOCO reference output")
    parser.add_argument("--validate-only", action="store_true", help="Validate canonical HTML and diagram sources")
    args = parser.parse_args()
    with site.build_lock():
        build(args)


def build(args: argparse.Namespace) -> None:
    site.validate_sources()
    if args.validate_only:
        print("Documentation HTML and diagram sources are valid.")
        return
    ontology.validate_publication_sources()
    destination = site.OUTPUT
    if args.quick and (destination / "ontology" / "index-en.html").is_file():
        site.CACHE.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="graph-candidate-", dir=site.CACHE) as directory:
            graph_directory = Path(directory)
            with ontology.site_output(graph_directory):
                ontology.build_relationship_graph()
            site.compose_site(graph_directory)
    else:
        build_root = site.ROOT / "build"
        build_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="documentation-candidate-", dir=build_root) as directory:
            candidate = Path(directory) / "site"
            with ontology.site_output(candidate):
                ontology.build_site(ontology._widoco_jar(None))
            site.OUTPUT = candidate
            try:
                site.compose_site()
                site.validate_published_links()
            finally:
                site.OUTPUT = destination
            for source in sorted(candidate.rglob("*")):
                if source.is_file():
                    site.publish_file(source, destination / source.relative_to(candidate))
    site.validate_published_links()
    print(f"Built documentation site at {destination}")


if __name__ == "__main__":
    main()
