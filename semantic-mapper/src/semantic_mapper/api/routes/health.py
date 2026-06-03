"""Health routes for the Semantic Mapper API."""

from fastapi import APIRouter


router = APIRouter()


@router.get("/healthz")
def healthz():
    """Return API health status."""

    return {"status": "ok"}
