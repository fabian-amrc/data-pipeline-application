"""Ontology discovery routes for the Semantic Mapper API."""

from fastapi import APIRouter

from semantic_mapper.api.services.ontologies import (
    identifier_scheme_payload,
    list_identifier_schemes,
    ontology_prefixes,
    ontology_summary,
    require_ontology,
    scheme_payload,
    term_payload,
)


router = APIRouter()


@router.get("/ontologies")
def list_ontologies():
    """Return registered ontologies."""

    return {"ontologies": [ontology_summary()]}


@router.get("/ontologies/{ontology_id}")
def get_ontology(ontology_id: str):
    """Return one ontology summary."""

    require_ontology(ontology_id)
    return ontology_summary(include_counts=True)


@router.get("/ontologies/{ontology_id}/prefixes")
def get_ontology_prefixes(ontology_id: str):
    """Return ontology prefixes."""

    require_ontology(ontology_id)
    return {"prefixes": ontology_prefixes()}


@router.get("/ontologies/{ontology_id}/terms/{term_id}")
def get_ontology_term(ontology_id: str, term_id: str):
    """Return ontology term metadata."""

    require_ontology(ontology_id)
    return term_payload(term_id)


@router.get("/ontologies/{ontology_id}/identifier-schemes")
def get_identifier_schemes(ontology_id: str):
    """Return identifier schemes for an ontology."""

    require_ontology(ontology_id)
    return {"identifier_schemes": [scheme_payload(scheme) for scheme in list_identifier_schemes().values()]}


@router.get("/ontologies/{ontology_id}/identifier-schemes/{scheme_id}")
def get_identifier_scheme(ontology_id: str, scheme_id: str):
    """Return one identifier scheme."""

    require_ontology(ontology_id)
    return identifier_scheme_payload(scheme_id)
