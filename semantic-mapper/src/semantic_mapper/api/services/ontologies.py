"""Ontology discovery and identifier scheme service functions."""

import json
from typing import Dict

from semantic_mapper.config import IDENTIFIER_SCHEMES_FILE, ONTOLOGY_DIR, ONTOLOGY_ID, PROFILE_IDS
from semantic_mapper.mapping.generator import IdentifierScheme
from semantic_mapper.rdf.files import read_all, ttl_files
from semantic_mapper.rdf.rml import parse_ontology_classes, parse_prefixes


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
