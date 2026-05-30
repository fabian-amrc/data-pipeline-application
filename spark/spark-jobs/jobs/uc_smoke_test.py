import json
import urllib.error
import urllib.request

from pyspark.sql import SparkSession


UC_URI = "http://unity-catalog-unitycatalog-server.unity-catalog.svc.cluster.local:8080"


def post_if_missing(path, payload, exists_statuses=(400, 409)):
    request = urllib.request.Request(
        f"{UC_URI}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response.read()
    except urllib.error.HTTPError as error:
        if error.code not in exists_statuses:
            raise


post_if_missing(
    "/api/2.1/unity-catalog/catalogs",
    {"name": "unity", "comment": "Local Spark smoke-test catalog"},
)
post_if_missing(
    "/api/2.1/unity-catalog/schemas",
    {
        "name": "default",
        "catalog_name": "unity",
        "comment": "Local Spark smoke-test schema",
    },
)

spark = SparkSession.builder.appName("unity-catalog-smoke-test").getOrCreate()

print("Spark version:", spark.version)
print("Unity Catalog schemas:")
spark.sql("SHOW SCHEMAS").show(truncate=False)

print("Unity Catalog default schema tables:")
spark.sql("SHOW TABLES IN default").show(truncate=False)

spark.stop()
