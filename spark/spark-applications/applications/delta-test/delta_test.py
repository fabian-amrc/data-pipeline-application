"""SparkApplication script that writes and reads a Delta table in MinIO."""

import os

from pyspark.sql import SparkSession
from pyspark.sql.types import IntegerType, StringType, StructField, StructType

from minio_s3 import (
    DEFAULT_AWS_REGION,
    DEFAULT_MINIO_ENDPOINT,
    bucket_from_s3a_uri,
    create_bucket_if_missing,
    resolve_minio_credentials,
)


DEFAULT_OUTPUT_PATH = "s3a://delta/delta-test"


output_path = os.getenv("OUTPUT_PATH", DEFAULT_OUTPUT_PATH)
endpoint = os.getenv("MINIO_ENDPOINT", DEFAULT_MINIO_ENDPOINT)
access_key, secret_key = resolve_minio_credentials()
region = os.getenv("AWS_REGION", DEFAULT_AWS_REGION)
bucket = bucket_from_s3a_uri(output_path, "OUTPUT_PATH")

create_bucket_if_missing(bucket, endpoint, access_key, secret_key, region)

spark = SparkSession.builder.appName("delta-minio-test").getOrCreate()
schema = StructType(
    [
        StructField("id", IntegerType(), True),
        StructField("name", StringType(), True),
        StructField("age", IntegerType(), True),
        StructField("city", StringType(), True),
    ]
)

data = [
    (1, "Alice", 28, "New York"),
    (2, "Bob", 34, "Los Angeles"),
    (3, "Charlie", 25, "Chicago"),
    (4, "David", 45, "San Francisco"),
    (5, "Eve", 30, "Boston"),
]

df = spark.createDataFrame(data, schema)

print("Spark version:", spark.version)
print("Writing Delta table to:", output_path)
df.show(truncate=False)

df.write.format("delta").mode("overwrite").save(output_path)

print("Reading Delta table from:", output_path)
delta_df = spark.read.format("delta").load(output_path)
delta_df.show(truncate=False)

row_count = delta_df.count()
print(f"Delta MinIO test complete. Read back {row_count} rows.")

spark.stop()
