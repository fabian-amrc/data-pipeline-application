"""Runtime configuration for the Semantic Mapper API."""

import os
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESOURCES_DIR = PACKAGE_ROOT / "resources"

ONTOLOGY_ID = os.getenv("ONTOLOGY_ID", "manufacturing-rdl")
PROFILE_IDS = ["spark-delta", "rml"]
STATE_DIR = Path(os.getenv("SEMANTIC_MAPPER_STATE_DIR", "/semantic-mapper/state"))
RESOURCES_DIR = Path(os.getenv("SEMANTIC_MAPPER_RESOURCES_DIR", str(DEFAULT_RESOURCES_DIR)))
ONTOLOGY_DIR = Path(os.getenv("ONTOLOGY_DIR", str(RESOURCES_DIR / "ontology")))
IDENTIFIER_SCHEMES_FILE = Path(
    os.getenv("IDENTIFIER_SCHEMES_FILE", str(ONTOLOGY_DIR / "identifier-schemes.json"))
)
FUSEKI_DATA_URL = os.getenv("FUSEKI_DATA_URL", "http://fuseki.fuseki.svc.cluster.local:3030/semantic/data")
FUSEKI_PING_URL = os.getenv("FUSEKI_PING_URL", "http://fuseki.fuseki.svc.cluster.local:3030/$/ping")
FUSEKI_USERNAME = os.getenv("FUSEKI_USERNAME", "admin")
FUSEKI_PASSWORD = os.getenv("FUSEKI_PASSWORD", "")
MAPPINGS_GRAPH_IRI = os.getenv("MAPPINGS_GRAPH_IRI", "https://data-pipeline.local/graph/mappings")
UNITY_CATALOG_API_URL = os.getenv(
    "UNITY_CATALOG_API_URL",
    "http://unity-catalog-unitycatalog-server.unity-catalog.svc.cluster.local:8080/api/2.1/unity-catalog",
)
