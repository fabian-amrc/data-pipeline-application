"""Unity Catalog projection routes for the Semantic Mapper API."""

from fastapi import APIRouter

from semantic_mapper.api.services.projections import project_mappings
from semantic_mapper.api.services.state import STORE


router = APIRouter()


@router.post("/projections/unity-catalog")
def post_project_all_unity_catalog():
    """Project all mappings into Unity Catalog."""

    return project_mappings([str(record["id"]) for record in STORE.list_mappings()])


@router.post("/mappings/{mapping_id}/project/unity-catalog")
def post_project_mapping_unity_catalog(mapping_id: str):
    """Project one mapping into Unity Catalog."""

    return project_mappings([mapping_id])


@router.get("/projection-jobs/{job_id}")
def get_projection_job(job_id: str):
    """Return one projection job."""

    job = STORE.get_projection_job(job_id)
    if not job:
        raise KeyError(job_id)
    return job
