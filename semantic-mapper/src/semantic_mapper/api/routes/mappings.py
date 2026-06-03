"""Mapping CRUD and RML routes for the Semantic Mapper API."""

import json
from typing import Dict

from fastapi import APIRouter, Request, Response, status

from semantic_mapper.api.services import STORE, create_rml_mapping, create_simple_mapping, mapping_response


router = APIRouter()


@router.post("/mappings", status_code=status.HTTP_201_CREATED)
def post_mapping(payload: Dict[str, object]):
    """Register a simple mapping payload."""

    return create_simple_mapping(payload)


@router.get("/mappings")
def list_mappings():
    """Return stored mapping records."""

    return {"mappings": STORE.list_mappings()}


@router.get("/mappings/{mapping_id}")
def get_mapping(mapping_id: str):
    """Return one stored mapping record."""

    return mapping_response(mapping_id)


@router.delete("/mappings/{mapping_id}")
def delete_mapping(mapping_id: str):
    """Delete one mapping."""

    STORE.delete_mapping(mapping_id)
    return {"deleted": mapping_id}


@router.post("/mappings/rml", status_code=status.HTTP_201_CREATED)
def post_rml_mapping(payload: Dict[str, object]):
    """Register expert-authored RML/Turtle."""

    return create_rml_mapping(payload)


@router.get("/mappings/{mapping_id}/rml")
def get_mapping_rml(mapping_id: str):
    """Return RML/Turtle for one mapping."""

    rml = STORE.get_rml(mapping_id)
    if rml is None:
        raise KeyError(mapping_id)
    return Response(content=rml, media_type="text/turtle")


@router.put("/mappings/{mapping_id}/rml")
async def put_mapping_rml(mapping_id: str, request: Request):
    """Replace RML/Turtle for one mapping."""

    body = (await request.body()).decode("utf-8")
    if request.headers.get("content-type", "").startswith("application/json"):
        rml = str(json.loads(body).get("ttl") or "")
    else:
        rml = body
    STORE.update_rml(mapping_id, rml)
    return mapping_response(mapping_id)
