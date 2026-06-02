"""Shared MinIO/S3 helpers for SparkApplication Python jobs.

The Spark applications mount this module from a generated ConfigMap rather than
baking it into the Spark image. It intentionally uses only the Python standard
library so the jobs can create MinIO buckets before writing Delta tables without
adding extra runtime dependencies.
"""

import datetime
import hashlib
import hmac
import os
import re
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_MINIO_ENDPOINT = "http://data-pipeline-hl.minio-tenant.svc.cluster.local:9000"
DEFAULT_AWS_REGION = "us-east-1"


def sign(key, message):
    """Return the AWS SigV4 HMAC-SHA256 digest for one signing step."""
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def signature_key(secret_key, date_stamp, region, service):
    """Derive the AWS SigV4 signing key for the given date, region, and service."""
    date_key = sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    region_key = sign(date_key, region)
    service_key = sign(region_key, service)
    return sign(service_key, "aws4_request")


def load_minio_env_file(path):
    """Parse the MinIO tenant config.env file mounted into Spark driver pods.

    The MinIO tenant secret stores shell-style export lines such as
    `export MINIO_ROOT_USER=...`. Missing files are treated as empty so callers
    can still rely on ordinary AWS_* or MINIO_* environment variables.
    """
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


def resolve_minio_credentials(env_file_path=None):
    """Resolve MinIO credentials from env vars or a mounted tenant config file.

    Precedence is AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY first, then
    MINIO_ACCESS_KEY/MINIO_SECRET_KEY, then MINIO_ROOT_USER/MINIO_ROOT_PASSWORD
    from the optional config.env file.
    """
    minio_env = load_minio_env_file(env_file_path)
    access_key = os.getenv(
        "AWS_ACCESS_KEY_ID",
        os.getenv("MINIO_ACCESS_KEY", minio_env.get("MINIO_ROOT_USER", "")),
    )
    secret_key = os.getenv(
        "AWS_SECRET_ACCESS_KEY",
        os.getenv("MINIO_SECRET_KEY", minio_env.get("MINIO_ROOT_PASSWORD", "")),
    )

    if not access_key or not secret_key:
        raise ValueError(
            "MinIO credentials are required. Set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY "
            "or mount the tenant config.env and set MINIO_CONFIG_ENV_FILE."
        )

    return access_key, secret_key


def bucket_from_s3a_uri(uri, field_name="S3A URI"):
    """Return the bucket name from an s3a URI and reject unsupported paths."""
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme != "s3a" or not parsed.netloc:
        raise ValueError(f"{field_name} must be an s3a URI with a bucket, got: {uri}")
    return parsed.netloc


def create_bucket_if_missing(endpoint, access_key, secret_key, bucket, region):
    """Create a MinIO bucket if it is absent.

    This sends a signed S3 `PUT /{bucket}` request using AWS SigV4. Existing
    buckets owned by the configured credentials are accepted as success.
    """
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
