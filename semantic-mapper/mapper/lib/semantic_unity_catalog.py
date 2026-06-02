"""Unity Catalog projection client for semantic mapper metadata.

This module turns ontology and mapping annotations into Unity Catalog catalogs,
schemas, and external Delta table metadata. It uses the UC REST API directly so
the mapper job does not need additional client dependencies.
"""

import json
import os
from pathlib import Path
from typing import Dict, List
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from lib.semantic_rdf import parse_mapping_projections, parse_ontology_classes


class UnityCatalogClient:
    """Minimal REST client for the Unity Catalog server API."""

    def __init__(self, api_url: str):
        """Store the base `/api/2.1/unity-catalog` URL."""
        self.api_url = api_url

    def headers(self, content_type: str) -> Dict[str, str]:
        """Build JSON request headers with an optional bearer token."""

        result = {"Content-Type": content_type}
        token = os.getenv("UNITY_CATALOG_BEARER_TOKEN")
        if token:
            result["Authorization"] = f"Bearer {token}"
        return result

    def request(self, path: str, method: str = "GET", payload=None, query=None):
        """Send a UC REST request and decode any JSON response body."""

        url = f"{self.api_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(url, data=data, method=method, headers=self.headers("application/json"))
        with urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else None

    def post_if_missing(self, path: str, payload: Dict[str, object], exists_statuses=(400, 409)) -> None:
        """POST a resource, treating configured conflict statuses as success."""

        try:
            status, _body = self.request(path, method="POST", payload=payload)
            print(f"Created Unity Catalog resource at {path}: HTTP {status}")
        except HTTPError as exc:
            if exc.code in exists_statuses:
                exc.read()
                return
            raise

    def get_table(self, full_name: str):
        """Return a UC table payload by full name, or None when absent."""

        try:
            _status, table = self.request(f"/tables/{quote(full_name, safe='')}")
            return table
        except HTTPError as exc:
            exc.read()
            if exc.code == 404:
                return None
            raise

    def ensure_namespace(self, catalog_name: str, schema_name: str) -> None:
        """Ensure the target catalog and schema exist before table creation."""

        self.post_if_missing(
            "/catalogs",
            {"name": catalog_name, "comment": "Local semantic mapper catalog"},
        )
        self.post_if_missing(
            "/schemas",
            {
                "name": schema_name,
                "catalog_name": catalog_name,
                "comment": "Local semantic mapper schema",
            },
        )

    def create_or_verify_table(
        self,
        projection: Dict[str, object],
        class_metadata: Dict[str, str],
        strict: bool,
    ) -> None:
        """Create a projected table or verify semantic metadata on an existing one."""

        full_name = str(projection["full_name"])
        class_iri = str(projection["class_iri"])
        storage_location = str(projection.get("storage_location") or "")
        columns = list(projection.get("columns") or [])

        if not storage_location or not columns:
            raise ValueError(
                f"Projection for {full_name} requires dpa:unityCatalogStorageLocation "
                "and at least one dpa:unityCatalogColumn."
            )

        name_parts = full_name.split(".")
        if len(name_parts) != 3:
            raise ValueError(f"Unity Catalog object must be catalog.schema.table: {full_name}")
        catalog_name, schema_name, table_name = name_parts
        self.ensure_namespace(catalog_name, schema_name)

        semantic_properties = {
            "semantic.class": class_iri,
            "semantic.label": class_metadata.get("label", ""),
            "semantic.source": "semantic-mapper",
        }
        existing = self.get_table(full_name)
        if existing:
            self._verify_existing_table(full_name, existing, semantic_properties, strict)
            return

        self._create_table(
            full_name,
            {
                "name": table_name,
                "catalog_name": catalog_name,
                "schema_name": schema_name,
                "table_type": "EXTERNAL",
                "data_source_format": "DELTA",
                "columns": columns,
                "storage_location": storage_location,
                "comment": class_metadata.get("comment") or class_metadata.get("label") or class_iri,
                "properties": semantic_properties,
            },
        )

    def _verify_existing_table(
        self,
        full_name: str,
        table: Dict[str, object],
        expected_properties: Dict[str, str],
        strict: bool,
    ) -> None:
        """Check whether an existing UC table carries expected semantic properties."""

        existing_properties = table.get("properties") or {}
        missing = {
            key: value
            for key, value in expected_properties.items()
            if existing_properties.get(key) != value
        }
        if not missing:
            print(f"Verified semantic metadata on UC table {full_name}")
            return

        message = (
            f"Unity Catalog table {full_name} already exists but cannot be updated "
            f"by this UC server. Missing/mismatched semantic properties: {missing}"
        )
        if strict:
            raise RuntimeError(message)
        print(f"WARNING: {message}")

    def _create_table(self, full_name: str, payload: Dict[str, object]) -> None:
        """Create a UC external Delta table from a prepared REST payload."""

        try:
            status, _table = self.request("/tables", method="POST", payload=payload)
            print(f"Projected semantic metadata by creating UC table {full_name}: HTTP {status}")
        except HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Unity Catalog table creation failed for {full_name}: "
                f"HTTP {exc.code} {message}"
            ) from exc


def project_to_unity_catalog(
    client: UnityCatalogClient,
    ontology_files: List[Path],
    mapping_files: List[Path],
    strict: bool,
) -> None:
    """Project all annotated mapping targets into Unity Catalog metadata."""

    classes = parse_ontology_classes(ontology_files)
    projections = parse_mapping_projections(mapping_files)
    if not projections:
        print("No mapping projections found. Add dpa:unityCatalogObject to a TriplesMap to enable UC projection.")
        return

    print(f"Found {len(projections)} Unity Catalog projection target(s)")
    for projection in projections:
        class_iri = str(projection["class_iri"])
        metadata = classes.get(class_iri, {"label": class_iri, "comment": ""})
        client.create_or_verify_table(projection, metadata, strict)
