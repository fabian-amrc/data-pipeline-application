import json
import urllib.parse
import urllib.request


def get_uc_table(api_url, full_name):
    encoded_name = urllib.parse.quote(full_name, safe="")
    request = urllib.request.Request(f"{api_url}/tables/{encoded_name}", method="GET")
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def verify_semantic_table(uc_info, full_name, output_path):
    properties = uc_info.get("properties") or {}
    if properties.get("semantic.class") != "https://data-pipeline.local/ontology/Dataset":
        raise RuntimeError(f"UC table {full_name} is missing semantic.class property: {properties}")

    expected_uc_storage = output_path.replace("s3a://", "s3://", 1)
    if uc_info.get("storage_location") != expected_uc_storage:
        raise RuntimeError(
            f"UC table {full_name} storage_location mismatch: "
            f"{uc_info.get('storage_location')} != {expected_uc_storage}"
        )
