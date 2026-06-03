"""Command-line entrypoint for running Semantic Mapper locally."""

import os

import uvicorn


def main() -> None:
    """Run the Semantic Mapper API with Uvicorn."""

    port = int(os.getenv("SEMANTIC_MAPPER_HTTP_PORT", os.getenv("PORT", "8000")))
    uvicorn.run("semantic_mapper.api.app:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
