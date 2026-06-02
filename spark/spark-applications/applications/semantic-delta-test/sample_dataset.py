"""Sample ontology-aligned dataset used by the semantic Delta SparkApplication."""

from pyspark.sql.types import IntegerType, StringType, StructField, StructType


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


def create_example_dataset(spark):
    """Create the semantic test DataFrame with the fixed schema and rows."""

    return spark.createDataFrame(DATA, SCHEMA)
