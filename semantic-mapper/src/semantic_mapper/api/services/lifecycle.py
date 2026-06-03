"""Mapping lifecycle service functions."""

from semantic_mapper.api.services.state import STORE
from semantic_mapper.clients.fuseki import FusekiClient
from semantic_mapper.config import (
    FUSEKI_DATA_URL,
    FUSEKI_PASSWORD,
    FUSEKI_PING_URL,
    FUSEKI_USERNAME,
    MAPPINGS_GRAPH_IRI,
)


def sync_mappings_graph() -> None:
    """Upload active mapping RML documents to Fuseki's mappings graph."""

    files = STORE.active_rml_files()
    fuseki = FusekiClient(FUSEKI_DATA_URL, FUSEKI_PING_URL, FUSEKI_USERNAME, FUSEKI_PASSWORD)
    fuseki.wait_until_ready(attempts=5, delay=1)
    fuseki.put_named_graph("mappings", files, MAPPINGS_GRAPH_IRI)
