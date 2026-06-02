import datetime
import hashlib
import hmac
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from pyspark.sql import SparkSession
from pyspark.sql.types import IntegerType, StringType, StructField, StructType


DEFAULT_ENDPOINT = "http://data-pipeline-hl.minio-tenant.svc.cluster.local:9000"
DEFAULT_OUTPUT_PATH = "s3a://delta/example-dataset"
DEFAULT_UC_TABLE = "unity.default.example_dataset"
DEFAULT_UC_API_URL = "http://unity-catalog-unitycatalog-server.unity-catalog.svc.cluster.local:8080/api/2.1/unity-catalog"


def sign(key, message):
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def signature_key(secret_key, date_stamp, region, service):
    date_key = sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    region_key = sign(date_key, region)
    service_key = sign(region_key, service)
    return sign(service_key, "aws4_request")


def load_minio_env_file(path):
    values = {}
    if not path or not os.path.exists(path):
        return values

    pattern = re.compile(r'^export\s+(MINIO_ROOT_USER|MINIO_ROOT_PASSWORD)="?([^"\n]+)"?\s*$')
    with open(path, encoding="utf-8") as env_file:
        for line in env_file:
            match = pattern.match(line.strip())
            if match:
                values[match.group(1)] = match.group(2)
    return values


def create_bucket_if_missing(endpoint, access_key, secret_key, bucket, region):
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"MINIO_ENDPOINT must be an http(s) URL, got: {endpoint}")

    now = datetime.datetime.now(datetime.UTC)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    path = f"/{bucket}"
    url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
    payload_hash = hashlib.sha256(b"").hexdigest()

    canonical_headers = (
        f"host:{parsed.netloc}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amz_date}\n"
    )
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical_request = "\n".join(
        ["PUT", path, "", canonical_headers, signed_headers, payload_hash]
    )
    credential_scope = f"{date_stamp}/{region}/s3/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    signature = hmac.new(
        signature_key(secret_key, date_stamp, region, "s3"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    authorization = (
        "AWS4-HMAC-SHA256 "
        f"Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )

    request = urllib.request.Request(
        url,
        method="PUT",
        headers={
            "Authorization": authorization,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            response.read()
            print(f"Bucket ready: {bucket} ({response.status})")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        if error.code == 409 and (
            "BucketAlreadyOwnedByYou" in body or "BucketAlreadyExists" in body
        ):
            print(f"Bucket already exists: {bucket}")
            return
        raise RuntimeError(
            f"Could not create bucket {bucket}: HTTP {error.code} {body}"
        ) from error


def configure_s3a(spark, endpoint, access_key, secret_key):
    hadoop_conf = spark.sparkContext._jsc.hadoopConfiguration()
    hadoop_conf.set("fs.s3a.endpoint", endpoint)
    hadoop_conf.set("fs.s3a.access.key", access_key)
    hadoop_conf.set("fs.s3a.secret.key", secret_key)
    hadoop_conf.set("fs.s3a.path.style.access", "true")
    hadoop_conf.set("fs.s3a.connection.ssl.enabled", str(endpoint.startswith("https")).lower())
    hadoop_conf.set("fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    hadoop_conf.set(
        "fs.s3a.aws.credentials.provider",
        "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
    )


def get_uc_table(api_url, full_name):
    encoded_name = urllib.parse.quote(full_name, safe="")
    request = urllib.request.Request(f"{api_url}/tables/{encoded_name}", method="GET")
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


output_path = os.getenv("OUTPUT_PATH", DEFAULT_OUTPUT_PATH)
endpoint = os.getenv("MINIO_ENDPOINT", DEFAULT_ENDPOINT)
uc_table = os.getenv("UC_TABLE", DEFAULT_UC_TABLE)
uc_api_url = os.getenv("UNITY_CATALOG_API_URL", DEFAULT_UC_API_URL)
minio_env = load_minio_env_file(os.getenv("MINIO_CONFIG_ENV_FILE"))
access_key = os.getenv(
    "AWS_ACCESS_KEY_ID",
    os.getenv("MINIO_ACCESS_KEY", minio_env.get("MINIO_ROOT_USER")),
)
secret_key = os.getenv(
    "AWS_SECRET_ACCESS_KEY",
    os.getenv("MINIO_SECRET_KEY", minio_env.get("MINIO_ROOT_PASSWORD")),
)
region = os.getenv("AWS_REGION", "us-east-1")
bucket = urllib.parse.urlparse(output_path).netloc

if not access_key or not secret_key:
    raise ValueError(
        "MinIO credentials are required. Set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY "
        "or mount the tenant config.env and set MINIO_CONFIG_ENV_FILE."
    )
if not bucket:
    raise ValueError(f"OUTPUT_PATH must be an s3a URI with a bucket, got: {output_path}")

create_bucket_if_missing(endpoint, access_key, secret_key, bucket, region)

spark = SparkSession.builder.appName("semantic-delta-test").getOrCreate()
configure_s3a(spark, endpoint, access_key, secret_key)

schema = StructType(
    [
        StructField("id", IntegerType(), True),
        StructField("name", StringType(), True),
        StructField("age", IntegerType(), True),
        StructField("city", StringType(), True),
    ]
)

data = [
    (1, "Ada", 37, "London"),
    (2, "Grace", 39, "Arlington"),
    (3, "Katherine", 44, "White Sulphur Springs"),
    (4, "Dorothy", 41, "Kansas City"),
]

df = spark.createDataFrame(data, schema)
print("Writing ontology-mapped Delta table to:", output_path)
df.show(truncate=False)
df.write.format("delta").mode("overwrite").save(output_path)

read_back = spark.read.format("delta").load(output_path)
row_count = read_back.count()
print(f"Read back {row_count} ontology-mapped Delta rows")
read_back.show(truncate=False)

uc_info = get_uc_table(uc_api_url, uc_table)
properties = uc_info.get("properties") or {}
if properties.get("semantic.class") != "https://data-pipeline.local/ontology/Dataset":
    raise RuntimeError(f"UC table {uc_table} is missing semantic.class property: {properties}")
expected_uc_storage = output_path.replace("s3a://", "s3://", 1)
if uc_info.get("storage_location") != expected_uc_storage:
    raise RuntimeError(
        f"UC table {uc_table} storage_location mismatch: "
        f"{uc_info.get('storage_location')} != {expected_uc_storage}"
    )
print("Verified UC semantic table registration:", json.dumps(uc_info, sort_keys=True))
print("Semantic Delta test complete.")

spark.stop()
