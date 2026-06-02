import json

from pyspark.sql import SparkSession

from minio_s3 import create_bucket_if_missing
from sample_dataset import create_example_dataset
from semantic_delta_config import load_settings
from semantic_uc import get_uc_table, verify_semantic_table


def main():
    settings = load_settings()
    create_bucket_if_missing(
        settings.endpoint,
        settings.access_key,
        settings.secret_key,
        settings.bucket,
        settings.region,
    )

    spark = SparkSession.builder.appName("semantic-delta-test").getOrCreate()
    try:
        df = create_example_dataset(spark)
        print("Writing ontology-mapped Delta table to:", settings.output_path)
        df.show(truncate=False)
        df.write.format("delta").mode("overwrite").save(settings.output_path)

        read_back = spark.read.format("delta").load(settings.output_path)
        row_count = read_back.count()
        print(f"Read back {row_count} ontology-mapped Delta rows")
        read_back.show(truncate=False)

        uc_info = get_uc_table(settings.uc_api_url, settings.uc_table)
        verify_semantic_table(uc_info, settings.uc_table, settings.output_path)
        print("Verified UC semantic table registration:", json.dumps(uc_info, sort_keys=True))
        print("Semantic Delta test complete.")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
