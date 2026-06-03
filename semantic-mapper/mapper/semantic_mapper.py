#!/usr/bin/env python3
"""Load semantic RDF into Fuseki and optionally project metadata into UC."""

import sys

from lib.semantic_config import load_settings
from lib.semantic_definitions import load_semantic_tables, write_generated_rml
from lib.semantic_files import ttl_files
from lib.semantic_fuseki import FusekiClient
from lib.semantic_unity_catalog import UnityCatalogClient, project_to_unity_catalog


def main() -> int:
    """Run the semantic mapper workflow and return a process exit code."""

    settings = load_settings()
    fuseki = FusekiClient(
        settings.fuseki_data_url,
        settings.fuseki_ping_url,
        settings.fuseki_username,
        settings.fuseki_password,
    )
    file_sets = {
        target.label: ttl_files(target.directory)
        for target in settings.graph_targets
    }
    semantic_tables = load_semantic_tables(settings.semantic_definitions_dir)
    generated_mapping_files = write_generated_rml(
        semantic_tables,
        settings.generated_mappings_dir / "spark-application-semantics.rml.ttl",
    )
    if generated_mapping_files:
        print(f"Generated {len(generated_mapping_files)} RML mapping file(s) from Spark semantics")
        file_sets["mappings"].extend(generated_mapping_files)

    fuseki.wait_until_ready()
    for target in settings.graph_targets:
        fuseki.put_named_graph(target.label, file_sets[target.label], target.graph_iri)

    if settings.project_to_unity_catalog:
        unity_catalog = UnityCatalogClient(settings.unity_catalog_api_url)
        project_to_unity_catalog(
            unity_catalog,
            file_sets["ontology"],
            file_sets["mappings"],
            settings.strict_unity_catalog_projection,
        )
    else:
        print("Unity Catalog projection disabled")

    return 0


if __name__ == "__main__":
    sys.exit(main())
