"""Build the complete static documentation website from HTML and diagram models."""

from __future__ import annotations

import argparse
from pathlib import Path
import tempfile

if __package__:
    from . import build_ontology_site as ontology
    from . import documentation_site as site
else:
    import build_ontology_site as ontology
    import documentation_site as site


def publish_candidate(candidate: Path, destination: Path) -> None:
    """Only validated derived output below build/ may be replaced or pruned."""
    resolved = destination.resolve()
    build_root = (site.ROOT / "build").resolve()
    if resolved == build_root or not resolved.is_relative_to(build_root):
        raise ValueError(f"Refusing to publish outside a derived build directory: {destination}")
    if destination.is_symlink() or destination.is_junction() or any(
        path.is_symlink() or path.is_junction() for path in destination.rglob("*")
    ):
        raise ValueError("Refusing to publish through a symlink or junction")
    expected = {source.relative_to(candidate) for source in candidate.rglob("*") if source.is_file()}
    for relative in sorted(expected):
        site.publish_file(candidate / relative, destination / relative)
    # WIDOCO/WebVOWL assets and deleted source routes must not survive a rebuild.
    for existing in sorted(destination.rglob("*"), reverse=True):
        if existing.is_file() and existing.relative_to(destination) not in expected:
            existing.unlink()
        elif existing.is_dir() and not any(existing.iterdir()):
            existing.rmdir()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Compatibility alias: every build refreshes graphs and RDF references")
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
    build_root = site.ROOT / "build"
    build_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="documentation-candidate-", dir=build_root) as directory:
        candidate = Path(directory) / "site"
        with ontology.site_output(candidate):
            ontology.build_site()
        site.OUTPUT = candidate
        try:
            site.compose_site()
            site.validate_published_links()
        finally:
            site.OUTPUT = destination
        publish_candidate(candidate, destination)
    site.validate_published_links()
    print(f"Built documentation site at {destination}")


if __name__ == "__main__":
    main()
