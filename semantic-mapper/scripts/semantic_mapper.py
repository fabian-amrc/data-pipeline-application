#!/usr/bin/env python3
import base64
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

ONTOLOGY_DIR = Path(os.getenv("ONTOLOGY_DIR", "/semantic-mapper/ontology"))
MAPPINGS_DIR = Path(os.getenv("MAPPINGS_DIR", "/semantic-mapper/mappings"))
SHAPES_DIR = Path(os.getenv("SHAPES_DIR", "/semantic-mapper/shapes"))

FUSEKI_DATA_URL = os.getenv("FUSEKI_DATA_URL", "http://fuseki.fuseki.svc.cluster.local:3030/semantic/data")
FUSEKI_PING_URL = os.getenv("FUSEKI_PING_URL", "http://fuseki.fuseki.svc.cluster.local:3030/$/ping")
FUSEKI_USERNAME = os.getenv("FUSEKI_USERNAME", "admin")
FUSEKI_PASSWORD = os.getenv("FUSEKI_PASSWORD")
UNITY_CATALOG_API_URL = os.getenv("UNITY_CATALOG_API_URL", "http://unity-catalog-unitycatalog-server.unity-catalog.svc.cluster.local:8080/api/2.1/unity-catalog")

GRAPH_TARGETS = [
    ("ontology", ONTOLOGY_DIR, os.getenv("ONTOLOGY_GRAPH_IRI", "https://data-pipeline.local/graph/ontology")),
    ("mappings", MAPPINGS_DIR, os.getenv("MAPPINGS_GRAPH_IRI", "https://data-pipeline.local/graph/mappings")),
    ("shapes", SHAPES_DIR, os.getenv("SHAPES_GRAPH_IRI", "https://data-pipeline.local/graph/shapes")),
]

PROJECT_TO_UC = os.getenv("PROJECT_TO_UNITY_CATALOG", "true").lower() == "true"
STRICT_UC = os.getenv("STRICT_UNITY_CATALOG_PROJECTION", "false").lower() == "true"

PREFIX_RE = re.compile(r"@prefix\s+([A-Za-z][\w-]*):\s+<([^>]+)>\s*\.")
CLASS_RE = re.compile(r"(?:^|[;\s])a\s+(?:owl:Class|rdfs:Class|<http://www\.w3\.org/2002/07/owl#Class>|<http://www\.w3\.org/2000/01/rdf-schema#Class>)")
LABEL_RE = re.compile(r"rdfs:label\s+\"([^\"]+)\"")
COMMENT_RE = re.compile(r"rdfs:comment\s+\"([^\"]+)\"")
RR_CLASS_RE = re.compile(r"rr:class\s+([^\s;\]]+)")
UC_OBJECT_RE = re.compile(r"dpa:unityCatalogObject\s+\"([^\"]+)\"")
UC_STORAGE_RE = re.compile(r"dpa:unityCatalogStorageLocation\s+\"([^\"]+)\"")
UC_COLUMN_RE = re.compile(r"dpa:unityCatalogColumn\s+\"([^\"]+)\"")

UC_TO_SPARK_JSON_TYPE = {
    "BOOLEAN": "boolean",
    "BYTE": "byte",
    "SHORT": "short",
    "INT": "integer",
    "LONG": "long",
    "FLOAT": "float",
    "DOUBLE": "double",
    "DATE": "date",
    "TIMESTAMP": "timestamp",
    "STRING": "string",
    "BINARY": "binary",
}


def ttl_files(directory: Path) -> List[Path]:
    return sorted(
        p
        for p in directory.rglob("*.ttl")
        if p.is_file() and not any(part.startswith("..") for part in p.parts)
    )


def read_all(files: Iterable[Path]) -> str:
    chunks = []
    for file in files:
        chunks.append(f"# Source: {file.name}\n")
        chunks.append(file.read_text(encoding="utf-8"))
        chunks.append("\n")
    return "".join(chunks)


def uc_headers(content_type: str) -> Dict[str, str]:
    result = {"Content-Type": content_type}
    token = os.getenv("UNITY_CATALOG_BEARER_TOKEN")
    if token:
        result["Authorization"] = f"Bearer {token}"
    return result


def fuseki_headers(content_type: str) -> Dict[str, str]:
    result = {"Content-Type": content_type}
    if FUSEKI_PASSWORD:
        credentials = f"{FUSEKI_USERNAME}:{FUSEKI_PASSWORD}".encode("utf-8")
        token = base64.b64encode(credentials).decode("ascii")
        result["Authorization"] = f"Basic {token}"
    return result




def uc_request(path: str, method: str = "GET", payload=None, query=None):
    url = f"{UNITY_CATALOG_API_URL}{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    data = None
    headers = uc_headers("application/json")
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, method=method, headers=headers)
    with urlopen(request, timeout=20) as response:
        body = response.read().decode("utf-8")
        return response.status, json.loads(body) if body else None


def post_if_missing(path: str, payload: Dict[str, object], exists_statuses=(400, 409)) -> None:
    try:
        status, _body = uc_request(path, method="POST", payload=payload)
        print(f"Created Unity Catalog resource at {path}: HTTP {status}")
    except HTTPError as exc:
        if exc.code in exists_statuses:
            exc.read()
            return
        raise


def get_uc_table(full_name: str):
    try:
        _status, table = uc_request(f"/tables/{quote(full_name, safe='')}")
        return table
    except HTTPError as exc:
        exc.read()
        if exc.code == 404:
            return None
        raise


def ensure_uc_namespace(catalog_name: str, schema_name: str) -> None:
    post_if_missing(
        "/catalogs",
        {"name": catalog_name, "comment": "Local semantic mapper catalog"},
    )
    post_if_missing(
        "/schemas",
        {
            "name": schema_name,
            "catalog_name": catalog_name,
            "comment": "Local semantic mapper schema",
        },
    )

def wait_for(url: str, attempts: int = 30, delay: float = 2.0) -> None:
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(url, timeout=5) as response:
                if 200 <= response.status < 500:
                    print(f"Ready: {url}")
                    return
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
        print(f"Waiting for {url} ({attempt}/{attempts})")
        time.sleep(delay)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def put_named_graph(label: str, files: List[Path], graph_iri: str) -> None:
    if not files:
        print(f"No {label} files found; skipping graph upload")
        return
    body = read_all(files).encode("utf-8")
    url = f"{FUSEKI_DATA_URL}?graph={quote(graph_iri, safe='')}"
    request = Request(url, data=body, method="PUT", headers=fuseki_headers("text/turtle"))
    with urlopen(request, timeout=30) as response:
        print(f"Uploaded {len(files)} {label} file(s) to {graph_iri}: HTTP {response.status}")


def parse_prefixes(text: str) -> Dict[str, str]:
    return dict(PREFIX_RE.findall(text))


def expand_term(term: str, prefixes: Dict[str, str]) -> str:
    term = term.strip()
    if term.startswith("<") and term.endswith(">"):
        return term[1:-1]
    if ":" in term:
        prefix, local = term.split(":", 1)
        if prefix in prefixes:
            return prefixes[prefix] + local
    return term


def statements(text: str) -> Iterable[str]:
    current = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("@prefix"):
            continue
        current.append(line)
        if stripped.endswith("."):
            yield "\n".join(current)
            current = []


def parse_ontology_classes(files: List[Path]) -> Dict[str, Dict[str, str]]:
    text = read_all(files)
    prefixes = parse_prefixes(text)
    classes: Dict[str, Dict[str, str]] = {}
    for statement in statements(text):
        if not CLASS_RE.search(statement):
            continue
        subject = statement.strip().split(None, 1)[0]
        iri = expand_term(subject, prefixes)
        label = LABEL_RE.search(statement)
        comment = COMMENT_RE.search(statement)
        classes[iri] = {
            "label": label.group(1) if label else iri.rsplit("/", 1)[-1],
            "comment": comment.group(1) if comment else "",
        }
    return classes


def parse_uc_columns(statement: str) -> List[Dict[str, object]]:
    columns = []
    for position, raw_column in enumerate(UC_COLUMN_RE.findall(statement)):
        parts = [part.strip() for part in raw_column.split(":", 2)]
        if len(parts) < 2:
            raise ValueError(f"Invalid dpa:unityCatalogColumn value: {raw_column}")
        name, type_name = parts[0], parts[1].upper()
        comment = parts[2] if len(parts) == 3 else ""
        spark_type = UC_TO_SPARK_JSON_TYPE.get(type_name)
        if not spark_type:
            raise ValueError(f"Unsupported dpa:unityCatalogColumn type: {type_name}")
        columns.append(
            {
                "name": name,
                "type_text": type_name,
                "type_json": json.dumps(
                    {
                        "name": name,
                        "type": spark_type,
                        "nullable": True,
                        "metadata": {},
                    },
                    separators=(",", ":"),
                ),
                "type_name": type_name,
                "position": position,
                "nullable": True,
                "comment": comment,
            }
        )
    return columns


def parse_mapping_projections(files: List[Path]) -> List[Dict[str, object]]:
    projections = []
    text = read_all(files)
    prefixes = parse_prefixes(text)
    for statement in statements(text):
        uc_object = UC_OBJECT_RE.search(statement)
        rr_class = RR_CLASS_RE.search(statement)
        storage_location = UC_STORAGE_RE.search(statement)
        if not uc_object or not rr_class:
            continue
        projections.append(
            {
                "full_name": uc_object.group(1),
                "class_iri": expand_term(rr_class.group(1), prefixes),
                "storage_location": storage_location.group(1) if storage_location else "",
                "columns": parse_uc_columns(statement),
            }
        )
    return projections


def create_or_verify_uc_table(projection: Dict[str, object], class_metadata: Dict[str, str]) -> None:
    full_name = str(projection["full_name"])
    class_iri = str(projection["class_iri"])
    storage_location = str(projection.get("storage_location") or "")
    columns = list(projection.get("columns") or [])

    if not storage_location or not columns:
        raise ValueError(
            f"Projection for {full_name} requires dpa:unityCatalogStorageLocation "
            "and at least one dpa:unityCatalogColumn."
        )

    name_parts = full_name.split(".")
    if len(name_parts) != 3:
        raise ValueError(f"Unity Catalog object must be catalog.schema.table: {full_name}")
    catalog_name, schema_name, table_name = name_parts
    ensure_uc_namespace(catalog_name, schema_name)

    semantic_properties = {
        "semantic.class": class_iri,
        "semantic.label": class_metadata.get("label", ""),
        "semantic.source": "semantic-mapper",
    }
    existing = get_uc_table(full_name)
    if existing:
        existing_properties = existing.get("properties") or {}
        missing = {
            key: value
            for key, value in semantic_properties.items()
            if existing_properties.get(key) != value
        }
        if missing:
            message = (
                f"Unity Catalog table {full_name} already exists but cannot be updated "
                f"by this UC server. Missing/mismatched semantic properties: {missing}"
            )
            if STRICT_UC:
                raise RuntimeError(message)
            print(f"WARNING: {message}")
        else:
            print(f"Verified semantic metadata on UC table {full_name}")
        return

    payload = {
        "name": table_name,
        "catalog_name": catalog_name,
        "schema_name": schema_name,
        "table_type": "EXTERNAL",
        "data_source_format": "DELTA",
        "columns": columns,
        "storage_location": storage_location,
        "comment": class_metadata.get("comment") or class_metadata.get("label") or class_iri,
        "properties": semantic_properties,
    }
    try:
        status, _table = uc_request("/tables", method="POST", payload=payload)
        print(f"Projected semantic metadata by creating UC table {full_name}: HTTP {status}")
    except HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Unity Catalog table creation failed for {full_name}: "
            f"HTTP {exc.code} {message}"
        ) from exc


def project_to_unity_catalog(ontology_files: List[Path], mapping_files: List[Path]) -> None:
    classes = parse_ontology_classes(ontology_files)
    projections = parse_mapping_projections(mapping_files)
    if not projections:
        print("No mapping projections found. Add dpa:unityCatalogObject to a TriplesMap to enable UC projection.")
        return
    print(f"Found {len(projections)} Unity Catalog projection target(s)")
    for projection in projections:
        class_iri = str(projection["class_iri"])
        metadata = classes.get(class_iri, {"label": class_iri, "comment": ""})
        create_or_verify_uc_table(projection, metadata)


def main() -> int:
    wait_for(FUSEKI_PING_URL)
    file_sets = {label: ttl_files(directory) for label, directory, _graph in GRAPH_TARGETS}
    for label, _directory, graph_iri in GRAPH_TARGETS:
        put_named_graph(label, file_sets[label], graph_iri)
    if PROJECT_TO_UC:
        project_to_unity_catalog(file_sets["ontology"], file_sets["mappings"])
    else:
        print("Unity Catalog projection disabled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
