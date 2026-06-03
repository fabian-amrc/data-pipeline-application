"""ASGI application for the Semantic Mapper REST API."""

import json
import sys
from typing import Dict
from urllib.parse import unquote

from semantic_mapper.clients.fuseki import FusekiClient
from semantic_mapper.clients.unity_catalog import UnityCatalogClient, project_to_unity_catalog
from semantic_mapper.config import (
    FUSEKI_DATA_URL,
    FUSEKI_PASSWORD,
    FUSEKI_PING_URL,
    FUSEKI_USERNAME,
    IDENTIFIER_SCHEMES_FILE,
    MAPPINGS_GRAPH_IRI,
    ONTOLOGY_DIR,
    ONTOLOGY_ID,
    PROFILE_IDS,
    STATE_DIR,
    UNITY_CATALOG_API_URL,
)
from semantic_mapper.mapping.generator import IdentifierScheme, generate_rml
from semantic_mapper.rdf.files import read_all, ttl_files
from semantic_mapper.rdf.rml import parse_mapping_projections, parse_ontology_classes, parse_prefixes
from semantic_mapper.storage import MappingStore


STORE = MappingStore(STATE_DIR)


async def app(scope, receive, send):
    """Handle one ASGI HTTP request."""

    if scope["type"] != "http":
        return
    request = Request(scope, receive)
    try:
        response = await dispatch(request)
    except Exception as exc:
        response = exception_response(exc)
    await response.send(send)


async def dispatch(request):
    """Route an HTTP request to the matching handler."""

    parts = request.path_parts
    method = request.method

    if method == "GET":
        if parts == ["healthz"]:
            return json_response({"status": "ok"})
        if parts == ["ontologies"]:
            return json_response({"ontologies": [ontology_summary()]})
        if len(parts) == 2 and parts[0] == "ontologies":
            require_ontology(parts[1])
            return json_response(ontology_summary(include_counts=True))
        if len(parts) == 3 and parts[:2] == ["ontologies", ONTOLOGY_ID] and parts[2] == "prefixes":
            return json_response({"prefixes": ontology_prefixes()})
        if len(parts) == 4 and parts[:2] == ["ontologies", ONTOLOGY_ID] and parts[2] == "terms":
            return json_response(term_payload(parts[3]))
        if len(parts) == 3 and parts[:2] == ["ontologies", ONTOLOGY_ID] and parts[2] == "identifier-schemes":
            return json_response({"identifier_schemes": [scheme_payload(scheme) for scheme in list_identifier_schemes().values()]})
        if len(parts) == 4 and parts[:2] == ["ontologies", ONTOLOGY_ID] and parts[2] == "identifier-schemes":
            return json_response(identifier_scheme_payload(parts[3]))
        if parts == ["mappings"]:
            return json_response({"mappings": STORE.list_mappings()})
        if len(parts) == 2 and parts[0] == "mappings":
            return json_response(mapping_response(parts[1]))
        if len(parts) == 3 and parts[0] == "mappings" and parts[2] == "rml":
            rml = STORE.get_rml(parts[1])
            if rml is None:
                return error_response(404, "mapping not found")
            return text_response(rml, "text/turtle")
        if len(parts) == 3 and parts[0] == "datasets" and parts[2] == "mappings":
            return json_response({"mappings": STORE.list_mappings(dataset_id=parts[1])})
        if len(parts) == 2 and parts[0] == "projection-jobs":
            job = STORE.get_projection_job(parts[1])
            if not job:
                return error_response(404, "projection job not found")
            return json_response(job)
        return error_response(404, "not found")

    if method == "POST":
        body = await request.json()
        if parts == ["mappings"]:
            return create_simple_mapping(body)
        if parts == ["mappings", "rml"]:
            return create_rml_mapping(body)
        if len(parts) == 3 and parts[0] == "mappings" and parts[2] == "validate":
            return json_response(validate_mapping(parts[1]))
        if len(parts) == 3 and parts[0] == "mappings" and parts[2] == "activate":
            mapping = STORE.set_status(parts[1], "active")
            sync_mappings_graph()
            return json_response(mapping)
        if len(parts) == 3 and parts[0] == "mappings" and parts[2] == "deprecate":
            mapping = STORE.set_status(parts[1], "deprecated")
            sync_mappings_graph()
            return json_response(mapping)
        if len(parts) == 3 and parts[0] == "datasets" and parts[2] == "inspect":
            return json_response({"dataset_id": parts[1], "columns": body.get("columns", [])})
        if parts == ["projections", "unity-catalog"]:
            return json_response(project_mappings([str(record["id"]) for record in STORE.list_mappings()]))
        if len(parts) == 4 and parts[0] == "mappings" and parts[2:] == ["project", "unity-catalog"]:
            return json_response(project_mappings([parts[1]]))
        return error_response(404, "not found")

    if method == "PUT":
        if len(parts) == 3 and parts[0] == "mappings" and parts[2] == "rml":
            rml = await request.text_or_json_ttl()
            STORE.update_rml(parts[1], rml)
            return json_response(mapping_response(parts[1]))
        return error_response(404, "not found")

    if method == "DELETE":
        if len(parts) == 2 and parts[0] == "mappings":
            STORE.delete_mapping(parts[1])
            return json_response({"deleted": parts[1]})
        return error_response(404, "not found")

    return error_response(405, "method not allowed")


class Request:
    """Small ASGI request wrapper."""

    def __init__(self, scope, receive):
        self.scope = scope
        self.receive = receive
        self.method = scope["method"]
        self.path_parts = [unquote(part) for part in scope.get("path", "").strip("/").split("/") if part]
        self.headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope.get("headers", [])}
        self._body = None

    async def body(self) -> bytes:
        """Read and cache the request body."""

        if self._body is not None:
            return self._body
        chunks = []
        more_body = True
        while more_body:
            message = await self.receive()
            chunks.append(message.get("body", b""))
            more_body = message.get("more_body", False)
        self._body = b"".join(chunks)
        return self._body

    async def json(self) -> Dict[str, object]:
        """Read a JSON request body."""

        data = await self.body()
        if not data:
            return {}
        return json.loads(data.decode("utf-8"))

    async def text_or_json_ttl(self) -> str:
        """Read RML from raw Turtle or a JSON `{ttl: ...}` body."""

        data = (await self.body()).decode("utf-8")
        if self.headers.get("content-type", "").startswith("application/json"):
            return str(json.loads(data).get("ttl") or "")
        return data


class Response:
    """Small ASGI response wrapper."""

    def __init__(self, body: bytes, status: int, content_type: str):
        self.body = body
        self.status = status
        self.content_type = content_type

    async def send(self, send):
        """Send the ASGI response."""

        await send(
            {
                "type": "http.response.start",
                "status": self.status,
                "headers": [
                    (b"content-type", self.content_type.encode("latin-1")),
                    (b"content-length", str(len(self.body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": self.body})


def json_response(payload, status=200):
    """Create a JSON response."""

    return Response(json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"), status, "application/json")


def text_response(text: str, content_type: str, status=200):
    """Create a text response."""

    return Response(text.encode("utf-8"), status, content_type)


def error_response(status: int, message: str):
    """Create a structured error response."""

    return json_response({"error": message}, status=status)


def exception_response(exc: Exception):
    """Convert known exceptions into HTTP errors."""

    if isinstance(exc, KeyError):
        return error_response(404, f"not found: {exc}")
    if isinstance(exc, ValueError):
        return error_response(400, str(exc))
    print(f"Unhandled error: {exc}", file=sys.stderr)
    return error_response(500, str(exc))


def create_simple_mapping(payload):
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
    return json_response(mapping_response(str(mapping["id"])), status=201)


def create_rml_mapping(payload):
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
    return json_response(mapping_response(str(mapping["id"])), status=201)


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
