"""Configuration model for the semantic Delta SparkApplication."""

import os
from dataclasses import dataclass

from minio_s3 import (
    DEFAULT_AWS_REGION,
    DEFAULT_MINIO_ENDPOINT,
    bucket_from_s3a_uri,
    resolve_minio_credentials,
)


DEFAULT_OUTPUT_PATH = "s3a://delta/example-dataset"
DEFAULT_UC_TABLE = "unity.default.example_dataset"
DEFAULT_UC_API_URL = "http://unity-catalog-unitycatalog-server.unity-catalog.svc.cluster.local:8080/api/2.1/unity-catalog"


@dataclass(frozen=True)
class SemanticDeltaTestSettings:
    """Resolved settings needed to write Delta data and verify UC metadata."""

    output_path: str
    endpoint: str
    uc_table: str
    uc_api_url: str
    access_key: str
    secret_key: str
    region: str
    bucket: str


def load_settings() -> SemanticDeltaTestSettings:
    """Load semantic Delta test settings from environment variables."""

    output_path = os.getenv("OUTPUT_PATH", DEFAULT_OUTPUT_PATH)
    access_key, secret_key = resolve_minio_credentials(os.getenv("MINIO_CONFIG_ENV_FILE"))
    bucket = bucket_from_s3a_uri(output_path, "OUTPUT_PATH")

    return SemanticDeltaTestSettings(
        output_path=output_path,
        endpoint=os.getenv("MINIO_ENDPOINT", DEFAULT_MINIO_ENDPOINT),
        uc_table=os.getenv("UC_TABLE", DEFAULT_UC_TABLE),
        uc_api_url=os.getenv("UNITY_CATALOG_API_URL", DEFAULT_UC_API_URL),
        access_key=access_key,
        secret_key=secret_key,
        region=os.getenv("AWS_REGION", DEFAULT_AWS_REGION),
        bucket=bucket,
    )
