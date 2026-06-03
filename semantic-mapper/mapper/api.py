#!/usr/bin/env python3
"""Semantic Mapper REST API.

The API accepts simple mapping JSON or expert-authored RML/Turtle, validates
it against the local ontology/RDL inputs, stores it centrally, and can project
mapping metadata to Unity Catalog.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict
from urllib.parse import unquote, urlparse

from lib.rdf.files import read_all, ttl_files
from lib.clients.fuseki import FusekiClient
from lib.mapping.generator import IdentifierScheme, generate_rml
from lib.rdf.rml import parse_mapping_projections, parse_ontology_classes, parse_prefixes
from lib.storage import MappingStore
from lib.clients.unity_catalog import UnityCatalogClient, project_to_unity_catalog


ONTOLOGY_ID = os.getenv("ONTOLOGY_ID", "manufacturing-rdl")
PROFILE_IDS = ["spark-delta", "rml"]
STATE_DIR = Path(os.getenv("SEMANTIC_MAPPER_STATE_DIR", "/semantic-mapper/state"))
ONTOLOGY_DIR = Path(os.getenv("ONTOLOGY_DIR", "/semantic-mapper/ontology"))
IDENTIFIER_SCHEMES_FILE = Path(
    os.getenv("IDENTIFIER_SCHEMES_FILE", "/semantic-mapper/ontology/identifier-schemes.json")
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

STORE = MappingStore(STATE_DIR)


class SemanticMapperHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the Semantic Mapper API."""

    server_version = "SemanticMapper/0.1"

    def do_GET(self):
        """Handle API read endpoints."""

        try:
            parts = path_parts(self.path)
            if parts == ["healthz"]:
                return self.respond({"status": "ok"})
            if parts == ["ontologies"]:
                return self.respond({"ontologies": [ontology_summary()]})
            if len(parts) == 2 and parts[0] == "ontologies":
                require_ontology(parts[1])
                return self.respond(ontology_summary(include_counts=True))
            if len(parts) == 3 and parts[:2] == ["ontologies", ONTOLOGY_ID] and parts[2] == "prefixes":
                return self.respond({"prefixes": ontology_prefixes()})
            if len(parts) == 4 and parts[:2] == ["ontologies", ONTOLOGY_ID] and parts[2] == "terms":
                return self.respond(term_payload(parts[3]))
            if len(parts) == 3 and parts[:2] == ["ontologies", ONTOLOGY_ID] and parts[2] == "identifier-schemes":
                return self.respond({"identifier_schemes": [scheme_payload(scheme) for scheme in list_identifier_schemes().values()]})
            if len(parts) == 4 and parts[:2] == ["ontologies", ONTOLOGY_ID] and parts[2] == "identifier-schemes":
                return self.respond(identifier_scheme_payload(parts[3]))
            if parts == ["mappings"]:
                return self.respond({"mappings": STORE.list_mappings()})
            if len(parts) == 2 and parts[0] == "mappings":
                return self.respond(mapping_response(parts[1]))
            if len(parts) == 3 and parts[0] == "mappings" and parts[2] == "rml":
                rml = STORE.get_rml(parts[1])
                if rml is None:
                    return self.error(404, "mapping not found")
                return self.respond_text(rml, "text/turtle")
            if len(parts) == 3 and parts[0] == "datasets" and parts[2] == "mappings":
                return self.respond({"mappings": STORE.list_mappings(dataset_id=parts[1])})
            if len(parts) == 2 and parts[0] == "projection-jobs":
                job = STORE.get_projection_job(parts[1])
                if not job:
                    return self.error(404, "projection job not found")
                return self.respond(job)
            return self.error(404, "not found")
        except Exception as exc:
            return self.exception(exc)

    def do_POST(self):
        """Handle API mutation and lifecycle endpoints."""

        try:
            parts = path_parts(self.path)
            body = self.read_json()
            if parts == ["mappings"]:
                return self.create_simple_mapping(body)
            if parts == ["mappings", "rml"]:
                return self.create_rml_mapping(body)
            if len(parts) == 3 and parts[0] == "mappings" and parts[2] == "validate":
                return self.respond(validate_mapping(parts[1]))
            if len(parts) == 3 and parts[0] == "mappings" and parts[2] == "activate":
                mapping = STORE.set_status(parts[1], "active")
                sync_mappings_graph()
                return self.respond(mapping)
            if len(parts) == 3 and parts[0] == "mappings" and parts[2] == "deprecate":
                mapping = STORE.set_status(parts[1], "deprecated")
                sync_mappings_graph()
                return self.respond(mapping)
            if len(parts) == 3 and parts[0] == "datasets" and parts[2] == "inspect":
                return self.respond({"dataset_id": parts[1], "columns": body.get("columns", [])})
            if parts == ["projections", "unity-catalog"]:
                return self.respond(project_mappings([str(record["id"]) for record in STORE.list_mappings()]))
            if len(parts) == 4 and parts[0] == "mappings" and parts[2:] == ["project", "unity-catalog"]:
                return self.respond(project_mappings([parts[1]]))
            return self.error(404, "not found")
        except Exception as exc:
            return self.exception(exc)

    def do_PUT(self):
        """Handle RML replacement."""

        try:
            parts = path_parts(self.path)
            if len(parts) == 3 and parts[0] == "mappings" and parts[2] == "rml":
                rml = self.read_text_or_json_ttl()
                STORE.update_rml(parts[1], rml)
                return self.respond(mapping_response(parts[1]))
            return self.error(404, "not found")
        except Exception as exc:
            return self.exception(exc)

    def do_DELETE(self):
        """Delete a mapping."""

        try:
            parts = path_parts(self.path)
            if len(parts) == 2 and parts[0] == "mappings":
                STORE.delete_mapping(parts[1])
                return self.respond({"deleted": parts[1]})
            return self.error(404, "not found")
        except Exception as exc:
            return self.exception(exc)

    def create_simple_mapping(self, payload):
        """Create a mapping from the simple Python DSL payload."""

        ontology = str(payload.get("ontology") or ONTOLOGY_ID)
        require_ontology(ontology)
        profile = str(payload.get("profile") or "spark-delta")
        if profile not in PROFILE_IDS:
            raise ValueError(f"Unsupported profile: {profile}")
        mapping_id = preview_mapping_id(payload)
        rml = generate_rml(mapping_id, payload, list_identifier_schemes())
        validate_rml_text(rml)
        mapping = STORE.create_mapping(source="simple", ontology=ontology, profile=profile, payload=payload, rml=rml)
        return self.respond(mapping_response(str(mapping["id"])), status=201)

    def create_rml_mapping(self, payload):
        """Create a mapping from expert-authored RML/Turtle."""

        ttl = str(payload.get("ttl") or "")
        if not ttl.strip():
            raise ValueError("ttl is required")
        validate_rml_text(ttl)
        mapping = STORE.create_mapping(
            source="rml",
            ontology=str(payload.get("ontology") or ONTOLOGY_ID),
            profile=str(payload.get("profile") or "rml"),
            rml=ttl,
        )
        return self.respond(mapping_response(str(mapping["id"])), status=201)

    def read_json(self):
        """Read a JSON request body."""

        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def read_text_or_json_ttl(self) -> str:
        """Read RML from raw Turtle or a JSON `{ttl: ...}` body."""

        length = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(length).decode("utf-8") if length else ""
        if self.headers.get("Content-Type", "").startswith("application/json"):
            return str(json.loads(data).get("ttl") or "")
        return data

    def respond(self, payload, status=200):
        """Write a JSON response."""

        data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def respond_text(self, text: str, content_type: str, status=200):
        """Write a text response."""

        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def error(self, status: int, message: str):
        """Write a structured error response."""

        return self.respond({"error": message}, status=status)

    def exception(self, exc: Exception):
        """Convert known exceptions into HTTP errors."""

        if isinstance(exc, KeyError):
            return self.error(404, f"not found: {exc}")
        if isinstance(exc, ValueError):
            return self.error(400, str(exc))
        print(f"Unhandled error: {exc}", file=sys.stderr)
        return self.error(500, str(exc))

    def log_message(self, fmt, *args):
        """Log requests to stderr with the default HTTP server format."""

        super().log_message(fmt, *args)


def path_parts(path: str):
    """Split a URL path into decoded route parts."""

    return [unquote(part) for part in urlparse(path).path.strip("/").split("/") if part]


def preview_mapping_id(payload: Dict[str, object]) -> str:
    """Create a readable mapping id seed for generated RML local names."""

    dataset = payload.get("dataset") or {}
    return "mapping-" + str(dataset.get("name") or "dataset").replace(".", "-")


def ontology_files():
    """Return ontology Turtle files."""

    return ttl_files(ONTOLOGY_DIR)


def ontology_text():
    """Return concatenated ontology text."""

    return read_all(ontology_files())


def ontology_summary(include_counts=False):
    """Return ontology metadata for API responses."""

    payload = {"id": ONTOLOGY_ID, "label": "Manufacturing RDL", "profiles": PROFILE_IDS}
    if include_counts:
        payload["class_count"] = len(parse_ontology_classes(ontology_files()))
        payload["identifier_scheme_count"] = len(list_identifier_schemes())
    return payload


def require_ontology(ontology_id: str) -> None:
    """Reject unknown ontology identifiers."""

    if ontology_id != ONTOLOGY_ID:
        raise ValueError(f"Unknown ontology: {ontology_id}")


def ontology_prefixes():
    """Return prefixes declared in ontology files."""

    return parse_prefixes(ontology_text())


def term_payload(term_id: str):
    """Return ontology class metadata by CURIE suffix or full IRI."""

    classes = parse_ontology_classes(ontology_files())
    for iri, metadata in classes.items():
        if term_id == iri or iri.endswith("/" + term_id) or iri.endswith("#" + term_id):
            return {"id": term_id, "iri": iri, **metadata}
    raise ValueError(f"Unknown ontology term: {term_id}")


def list_identifier_schemes() -> Dict[str, IdentifierScheme]:
    """Load centrally-defined identifier schemes."""

    data = json.loads(IDENTIFIER_SCHEMES_FILE.read_text(encoding="utf-8"))
    return {
        item["id"]: IdentifierScheme(id=item["id"], label=item.get("label", item["id"]), template=item["template"])
        for item in data.get("schemes", [])
    }


def identifier_scheme_payload(scheme_id: str):
    """Return one identifier scheme by id."""

    schemes = list_identifier_schemes()
    if scheme_id not in schemes:
        raise ValueError(f"Unknown identifier scheme: {scheme_id}")
    return scheme_payload(schemes[scheme_id])


def scheme_payload(scheme: IdentifierScheme):
    """Return a JSON-safe identifier scheme payload."""

    return {"id": scheme.id, "label": scheme.label, "template": scheme.template}


def validate_rml_text(rml: str) -> Dict[str, object]:
    """Validate RML enough for storage and UC projection."""

    tmp = STATE_DIR / ".validation.rml.ttl"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(rml, encoding="utf-8")
    projections = parse_mapping_projections([tmp])
    classes = parse_ontology_classes(ontology_files())
    warnings = []
    for projection in projections:
        class_iri = str(projection["class_iri"])
        if class_iri not in classes:
            warnings.append(f"Class not found in ontology: {class_iri}")
    return {"valid": True, "projection_count": len(projections), "warnings": warnings}


def validate_mapping(mapping_id: str) -> Dict[str, object]:
    """Validate a stored mapping."""

    rml = STORE.get_rml(mapping_id)
    if rml is None:
        raise KeyError(mapping_id)
    return validate_rml_text(rml)


def mapping_response(mapping_id: str) -> Dict[str, object]:
    """Return mapping metadata with validation summary."""

    mapping = STORE.require_mapping(mapping_id)
    return {**mapping, "validation": validate_mapping(mapping_id)}


def sync_mappings_graph() -> None:
    """Upload active mapping RML documents to Fuseki's mappings graph."""

    files = STORE.active_rml_files()
    fuseki = FusekiClient(FUSEKI_DATA_URL, FUSEKI_PING_URL, FUSEKI_USERNAME, FUSEKI_PASSWORD)
    fuseki.wait_until_ready(attempts=5, delay=1)
    fuseki.put_named_graph("mappings", files, MAPPINGS_GRAPH_IRI)


def project_mappings(mapping_ids):
    """Project stored mappings into Unity Catalog and persist a job record."""

    files = STORE.rml_files(mapping_ids)
    client = UnityCatalogClient(UNITY_CATALOG_API_URL)
    project_to_unity_catalog(client, ontology_files(), files, strict=True)
    return STORE.create_projection_job({"mapping_ids": mapping_ids, "target": "unity-catalog"})


def configured_port() -> int:
    """Return the HTTP bind port without using Kubernetes service-link values."""

    explicit_port = os.getenv("SEMANTIC_MAPPER_HTTP_PORT")
    legacy_port = os.getenv("SEMANTIC_MAPPER_PORT")
    port_value = explicit_port or (legacy_port if legacy_port and legacy_port.isdigit() else "8080")
    try:
        return int(port_value)
    except ValueError as exc:
        raise ValueError(f"SEMANTIC_MAPPER_HTTP_PORT must be an integer, got {port_value!r}") from exc


def main():
    """Run the REST API server."""

    port = configured_port()
    server = ThreadingHTTPServer(("0.0.0.0", port), SemanticMapperHandler)
    print(f"Semantic Mapper API listening on :{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
