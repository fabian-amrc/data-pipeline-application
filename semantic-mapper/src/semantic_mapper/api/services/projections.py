"""Metadata projection service functions."""

from semantic_mapper.api.services.ontologies import ontology_files
from semantic_mapper.api.services.state import STORE
from semantic_mapper.clients.unity_catalog import UnityCatalogClient, project_to_unity_catalog
from semantic_mapper.config import UNITY_CATALOG_API_URL


def project_mappings(mapping_ids):
    """Project stored mappings into Unity Catalog and persist a job record."""

    files = STORE.rml_files(mapping_ids)
    client = UnityCatalogClient(UNITY_CATALOG_API_URL)
    project_to_unity_catalog(client, ontology_files(), files, strict=True)
    return STORE.create_projection_job({"mapping_ids": mapping_ids, "target": "unity-catalog"})
