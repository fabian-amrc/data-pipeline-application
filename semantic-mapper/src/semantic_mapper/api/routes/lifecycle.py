"""Mapping lifecycle routes for the Semantic Mapper API."""

from fastapi import APIRouter

from semantic_mapper.api.services.lifecycle import sync_mappings_graph
from semantic_mapper.api.services.mappings import validate_mapping
from semantic_mapper.api.services.state import STORE


router = APIRouter()


@router.post("/mappings/{mapping_id}/validate")
def post_validate_mapping(mapping_id: str):
    """Validate a stored mapping."""

    return validate_mapping(mapping_id)


@router.post("/mappings/{mapping_id}/activate")
def post_activate_mapping(mapping_id: str):
    """Activate a mapping and sync active RML to Fuseki."""

    mapping = STORE.set_status(mapping_id, "active")
    sync_mappings_graph()
    return mapping


@router.post("/mappings/{mapping_id}/deprecate")
def post_deprecate_mapping(mapping_id: str):
    """Deprecate a mapping and sync active RML to Fuseki."""

    mapping = STORE.set_status(mapping_id, "deprecated")
    sync_mappings_graph()
    return mapping
