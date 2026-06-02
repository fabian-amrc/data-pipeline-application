import os
import urllib.parse
from dataclasses import dataclass

from minio_s3 import load_minio_env_file


DEFAULT_ENDPOINT = "http://data-pipeline-hl.minio-tenant.svc.cluster.local:9000"
DEFAULT_OUTPUT_PATH = "s3a://delta/example-dataset"
DEFAULT_UC_TABLE = "unity.default.example_dataset"
DEFAULT_UC_API_URL = "http://unity-catalog-unitycatalog-server.unity-catalog.svc.cluster.local:8080/api/2.1/unity-catalog"


@dataclass(frozen=True)
class SemanticDeltaTestSettings:
    output_path: str
    endpoint: str
    uc_table: str
    uc_api_url: str
    access_key: str
    secret_key: str
    region: str
    bucket: str


def load_settings() -> SemanticDeltaTestSettings:
    output_path = os.getenv("OUTPUT_PATH", DEFAULT_OUTPUT_PATH)
    minio_env = load_minio_env_file(os.getenv("MINIO_CONFIG_ENV_FILE"))
    access_key = os.getenv(
        "AWS_ACCESS_KEY_ID",
        os.getenv("MINIO_ACCESS_KEY", minio_env.get("MINIO_ROOT_USER", "")),
    )
    secret_key = os.getenv(
        "AWS_SECRET_ACCESS_KEY",
        os.getenv("MINIO_SECRET_KEY", minio_env.get("MINIO_ROOT_PASSWORD", "")),
    )
    bucket = urllib.parse.urlparse(output_path).netloc

    if not access_key or not secret_key:
        raise ValueError(
            "MinIO credentials are required. Set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY "
            "or mount the tenant config.env and set MINIO_CONFIG_ENV_FILE."
        )
    if not bucket:
        raise ValueError(f"OUTPUT_PATH must be an s3a URI with a bucket, got: {output_path}")

    return SemanticDeltaTestSettings(
        output_path=output_path,
        endpoint=os.getenv("MINIO_ENDPOINT", DEFAULT_ENDPOINT),
        uc_table=os.getenv("UC_TABLE", DEFAULT_UC_TABLE),
        uc_api_url=os.getenv("UNITY_CATALOG_API_URL", DEFAULT_UC_API_URL),
        access_key=access_key,
        secret_key=secret_key,
        region=os.getenv("AWS_REGION", "us-east-1"),
        bucket=bucket,
    )
