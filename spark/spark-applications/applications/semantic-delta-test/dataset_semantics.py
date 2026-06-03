"""Semantic declaration for the example dataset written by this Spark app."""

from semantic_mapping import column, semantic_table


EXAMPLE_DATASET_SEMANTICS = semantic_table(
    mapping_id="ExampleDatasetMapping",
    full_name="unity.default.example_dataset",
    class_iri="https://data-pipeline.local/ontology/Dataset",
    storage_location="s3://delta/example-dataset",
    source_uri="s3a://delta/example-dataset",
    subject_template="https://data-pipeline.local/resource/dataset/{id}",
    columns=[
        column("id", "INT", "Dataset identifier"),
        column("name", "STRING", "Display name"),
        column("age", "INT", "Example numeric attribute"),
        column("city", "STRING", "Example city attribute"),
    ],
)

SEMANTIC_TABLES = [EXAMPLE_DATASET_SEMANTICS]
