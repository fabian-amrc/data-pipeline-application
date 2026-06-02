"""SparkApplication script that smoke-tests Spark connectivity to Unity Catalog."""

import json
import urllib.error
import urllib.request

from pyspark.sql import SparkSession


def get_json(path):
    """Fetch and decode JSON from the Unity Catalog smoke-test server URL."""

    request = urllib.request.Request(f"{UC_URI}{path}", method="GET")
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


UC_URI = "http://unity-catalog-unitycatalog-server.unity-catalog.svc.cluster.local:8080"


def post_if_missing(path, payload, exists_statuses=(400, 409)):
    """Create a UC resource, ignoring response codes that mean it already exists."""

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
print("Unity Catalog REST catalogs:")
print(json.dumps(get_json("/api/2.1/unity-catalog/catalogs"), indent=2, sort_keys=True))

print("Spark current catalog:")
spark.sql("SELECT current_catalog() AS catalog, current_database() AS schema").show(truncate=False)

print("Spark catalogs:")
spark.sql("SHOW CATALOGS").show(truncate=False)

print("Unity Catalog schemas in current catalog:")
spark.sql("SHOW SCHEMAS").show(truncate=False)

print("Unity Catalog default schema tables:")
spark.sql("SHOW TABLES IN default").show(truncate=False)

spark.stop()
