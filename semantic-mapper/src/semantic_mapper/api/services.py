"""Shared API service functions for ontology, mapping, and projection routes."""

import json
from typing import Dict

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
    return mapping_response(str(mapping["id"]))


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
    return mapping_response(str(mapping["id"]))


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
