import os
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class GraphTarget:
    label: str
    directory: Path
    graph_iri: str


@dataclass(frozen=True)
class SemanticMapperSettings:
    fuseki_data_url: str
    fuseki_ping_url: str
    fuseki_username: str
    fuseki_password: str
    unity_catalog_api_url: str
    project_to_unity_catalog: bool
    strict_unity_catalog_projection: bool
    graph_targets: List[GraphTarget]


def env_flag(name: str, default: bool) -> bool:
    default_text = "true" if default else "false"
    return os.getenv(name, default_text).lower() == "true"


def load_settings() -> SemanticMapperSettings:
    ontology_dir = Path(os.getenv("ONTOLOGY_DIR", "/semantic-mapper/ontology"))
    mappings_dir = Path(os.getenv("MAPPINGS_DIR", "/semantic-mapper/mappings"))
    shapes_dir = Path(os.getenv("SHAPES_DIR", "/semantic-mapper/shapes"))

    return SemanticMapperSettings(
        fuseki_data_url=os.getenv(
            "FUSEKI_DATA_URL",
            "http://fuseki.fuseki.svc.cluster.local:3030/semantic/data",
        ),
        fuseki_ping_url=os.getenv(
            "FUSEKI_PING_URL",
            "http://fuseki.fuseki.svc.cluster.local:3030/$/ping",
        ),
        fuseki_username=os.getenv("FUSEKI_USERNAME", "admin"),
        fuseki_password=os.getenv("FUSEKI_PASSWORD", ""),
        unity_catalog_api_url=os.getenv(
            "UNITY_CATALOG_API_URL",
            "http://unity-catalog-unitycatalog-server.unity-catalog.svc.cluster.local:8080/api/2.1/unity-catalog",
        ),
        project_to_unity_catalog=env_flag("PROJECT_TO_UNITY_CATALOG", True),
        strict_unity_catalog_projection=env_flag("STRICT_UNITY_CATALOG_PROJECTION", False),
        graph_targets=[
            GraphTarget(
                "ontology",
                ontology_dir,
                os.getenv("ONTOLOGY_GRAPH_IRI", "https://data-pipeline.local/graph/ontology"),
            ),
            GraphTarget(
                "mappings",
                mappings_dir,
                os.getenv("MAPPINGS_GRAPH_IRI", "https://data-pipeline.local/graph/mappings"),
            ),
            GraphTarget(
                "shapes",
                shapes_dir,
                os.getenv("SHAPES_GRAPH_IRI", "https://data-pipeline.local/graph/shapes"),
            ),
        ],
    )
