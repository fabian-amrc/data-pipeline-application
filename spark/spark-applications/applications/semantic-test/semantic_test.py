"""SparkApplication script for semantic Delta data and metadata registration."""

import json
import os

from pyspark.sql import SparkSession
from pyspark.sql.types import IntegerType, StringType, StructField, StructType

from semantic_mapper import SemanticMapper
from minio_s3 import (
    DEFAULT_AWS_REGION,
    DEFAULT_MINIO_ENDPOINT,
    bucket_from_s3a_uri,
    create_bucket_if_missing,
    resolve_minio_credentials,
)
from semantic_uc import get_uc_table, verify_semantic_table

# Configuration for the semantic test, with defaults and environment variable overrides.
DATASET_NAME = "unity.default.example_dataset"
SOURCE_URI = "s3a://delta/example-dataset"
RDF_CLASS = "dpa:Dataset"
RDF_CLASS_IRI = "https://data-pipeline.local/ontology/Dataset"
DEFAULT_UC_API_URL = "http://unity-catalog-unitycatalog-server.unity-catalog.svc.cluster.local:8080/api/2.1/unity-catalog"

OUTPUT_PATH = os.getenv("OUTPUT_PATH", SOURCE_URI)
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", DEFAULT_MINIO_ENDPOINT)
UC_TABLE = os.getenv("UC_TABLE", DATASET_NAME)
UC_API_URL = os.getenv("UNITY_CATALOG_API_URL", DEFAULT_UC_API_URL)
ACCESS_KEY, SECRET_KEY = resolve_minio_credentials()
AWS_REGION = os.getenv("AWS_REGION", DEFAULT_AWS_REGION)
BUCKET = bucket_from_s3a_uri(OUTPUT_PATH, "OUTPUT_PATH")


# Example dataset schema and data to write as Delta and register with UC semantics.
SCHEMA = StructType(
    [
        StructField("id", IntegerType(), True),
        StructField("name", StringType(), True),
        StructField("age", IntegerType(), True),
        StructField("city", StringType(), True),
    ]
)
DATA = [
    (1, "Ada", 37, "London"),
    (2, "Grace", 39, "Arlington"),
    (3, "Katherine", 44, "White Sulphur Springs"),
    (4, "Dorothy", 41, "Kansas City"),
]


def storage_location_for(source_uri):
    """Return the Unity Catalog storage URI for a Spark S3A source URI."""

    return source_uri.replace("s3a://", "s3://", 1)


def main():
    """Write Delta data, register semantics, and verify Unity Catalog metadata."""

    create_bucket_if_missing(
        MINIO_ENDPOINT,
        ACCESS_KEY,
        SECRET_KEY,
        BUCKET,
        AWS_REGION,
    )

    spark = SparkSession.builder.appName("semantic-test").getOrCreate()
    try:
        df = spark.createDataFrame(DATA, SCHEMA)
        print("Writing semantic Delta table to:", OUTPUT_PATH)
        df.show(truncate=False)
        df.write.format("delta").mode("overwrite").save(OUTPUT_PATH)

        read_back = spark.read.format("delta").load(OUTPUT_PATH)
        row_count = read_back.count()
        print(f"Read back {row_count} semantic Delta rows")
        read_back.show(truncate=False)

        storage_location = storage_location_for(OUTPUT_PATH)
        mapper = SemanticMapper()
        dataset = mapper.dataset(UC_TABLE)
        dataset.row_subject(rdf_class=RDF_CLASS)
        dataset.subject_identifier(column="id", scheme="dpa:dataset-id")
        dataset.storage(source_uri=OUTPUT_PATH, storage_location=storage_location)
        dataset.column("id", "INT", "Dataset identifier").literal(predicate="dpa:datasetId")
        dataset.column("name", "STRING", "Display name").literal(predicate="dpa:name")
        dataset.column("age", "INT", "Example numeric attribute").literal(predicate="dpa:age")
        dataset.column("city", "STRING", "Example city attribute").classification(term="dpa:LocationAttribute")
        registration = dataset.register_and_project()
        print("Registered semantic mapping:", json.dumps(registration, sort_keys=True))

        uc_info = get_uc_table(UC_API_URL, UC_TABLE)
        verify_semantic_table(uc_info, UC_TABLE, RDF_CLASS_IRI, storage_location)
        print("Verified UC semantic table registration:", json.dumps(uc_info, sort_keys=True))
        print("Semantic test complete.")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
