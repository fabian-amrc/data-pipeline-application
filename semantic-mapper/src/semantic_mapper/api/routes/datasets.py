"""Dataset routes for the Semantic Mapper API."""

from typing import Dict

from fastapi import APIRouter

from semantic_mapper.api.services.state import STORE


router = APIRouter()


@router.post("/datasets/{dataset_id}/inspect")
def inspect_dataset(dataset_id: str, payload: Dict[str, object]):
    """Return inspected dataset columns from a caller-provided payload."""

    return {"dataset_id": dataset_id, "columns": payload.get("columns", [])}


@router.get("/datasets/{dataset_id}/mappings")
def dataset_mappings(dataset_id: str):
    """Return mappings registered for one dataset id."""

    return {"mappings": STORE.list_mappings(dataset_id=dataset_id)}
