"""Mapping creation, response, and validation service functions."""

from typing import Dict

from semantic_mapper.api.services.ontologies import list_identifier_schemes, ontology_files, require_ontology
from semantic_mapper.api.services.state import STORE
from semantic_mapper.config import ONTOLOGY_ID, PROFILE_IDS, STATE_DIR
from semantic_mapper.mapping.generator import generate_rml
from semantic_mapper.rdf.rml import parse_mapping_projections, parse_ontology_classes


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
