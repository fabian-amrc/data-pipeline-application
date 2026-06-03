"""FastAPI application for the Semantic Mapper REST API."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from semantic_mapper.api.routes import datasets, health, lifecycle, mappings, ontologies, projections


app = FastAPI(title="Semantic Mapper", version="0.1.0")
app.include_router(health.router)
app.include_router(ontologies.router)
app.include_router(mappings.router)
app.include_router(lifecycle.router)
app.include_router(datasets.router)
app.include_router(projections.router)


@app.exception_handler(KeyError)
async def key_error_handler(_request: Request, exc: KeyError):
    """Return the API's existing not-found error shape for missing records."""

    return JSONResponse({"error": f"not found: {exc}"}, status_code=404)


@app.exception_handler(ValueError)
async def value_error_handler(_request: Request, exc: ValueError):
    """Return the API's existing bad-request error shape for validation errors."""

    return JSONResponse({"error": str(exc)}, status_code=400)
