"""Unity Catalog assertions for semantic-test."""

import json
import os
import urllib.parse
import urllib.request


UC_API_URL = "http://unity-catalog-unitycatalog-server.unity-catalog.svc.cluster.local:8080/api/2.1/unity-catalog"


def get_uc_table(full_name, api_url = None):
    """Fetch one Unity Catalog table by fully-qualified table name."""

    api_url = api_url or os.getenv("UC_API_URL", UC_API_URL)

    encoded_name = urllib.parse.quote(full_name, safe="")
    request = urllib.request.Request(f"{api_url}/tables/{encoded_name}", method="GET")
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def verify_semantic_table(uc_info, full_name, class_iri, storage_location):
    """Assert that UC metadata matches the registered semantic mapping."""

    properties = uc_info.get("properties") or {}
    if properties.get("semantic.class") != class_iri:
        raise RuntimeError(f"UC table {full_name} is missing semantic.class property: {properties}")

    if uc_info.get("storage_location") != storage_location:
        raise RuntimeError(
            f"UC table {full_name} storage_location mismatch: "
            f"{uc_info.get('storage_location')} != {storage_location}"
        )
