"""SparkApplication script for semantic Delta data and metadata registration."""

import json
import os

from pyspark.sql import SparkSession
from pyspark.sql.types import IntegerType, StringType, StructField, StructType

from semantic_mapper import SemanticMapper
from minio_s3 import bucket_from_s3a_uri, create_bucket_if_missing
from semantic_uc import get_uc_table, verify_semantic_table


# Configuration for the semantic test
DATASET_NAME = "unity.default.example_dataset"
SOURCE_URI = "s3a://delta/example-dataset"
RDF_CLASS = "dpa:Dataset"
RDF_CLASS_IRI = "https://w3id.org/amrc/manufacturing-rdl/dataset#Dataset"


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


def main():
    """Write Delta data, register semantics, and verify Unity Catalog metadata."""

    create_bucket_if_missing(bucket_from_s3a_uri(SOURCE_URI, "SOURCE_URI"))

    spark = SparkSession.builder.appName("semantic-test").getOrCreate()
    try:
        df = spark.createDataFrame(DATA, SCHEMA)
        print("Writing semantic Delta table to:", SOURCE_URI)
        df.show(truncate=False)
        df.write.format("delta").mode("overwrite").save(SOURCE_URI)

        read_back = spark.read.format("delta").load(SOURCE_URI)
        row_count = read_back.count()
        print(f"Read back {row_count} semantic Delta rows")
        read_back.show(truncate=False)

        storage_location = SOURCE_URI.replace("s3a://", "s3://", 1)
        mapper = SemanticMapper()
        dataset = mapper.dataset(DATASET_NAME)
        dataset.row_subject(rdf_class=RDF_CLASS)
        dataset.subject_identifier(column="id", scheme="dpa:dataset-id")
        dataset.storage(source_uri=SOURCE_URI, storage_location=storage_location)
        dataset.column("id", "INT", "Dataset identifier").literal(predicate="dpa:datasetId")
        dataset.column("name", "STRING", "Display name").literal(predicate="dpa:name")
        dataset.column("age", "INT", "Example numeric attribute").literal(predicate="dpa:age")
        dataset.column("city", "STRING", "Example city attribute").classification(term="dpa:LocationAttribute")
        registration = dataset.register_and_project()
        print("Registered semantic mapping:", json.dumps(registration, sort_keys=True))

        uc_info = get_uc_table(DATASET_NAME)
        verify_semantic_table(uc_info, DATASET_NAME, RDF_CLASS_IRI, storage_location)
        print("Verified UC semantic table registration:", json.dumps(uc_info, sort_keys=True))
        print("Semantic test complete.")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
