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
from urllib.parse import quote
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


def ttl_files(directory: Path) -> List[Path]:
    return sorted(p for p in directory.rglob("*.ttl") if p.is_file())


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


def parse_mapping_projections(files: List[Path]) -> List[Tuple[str, str]]:
    projections = []
    text = read_all(files)
    prefixes = parse_prefixes(text)
    for statement in statements(text):
        uc_object = UC_OBJECT_RE.search(statement)
        rr_class = RR_CLASS_RE.search(statement)
        if not uc_object or not rr_class:
            continue
        projections.append((uc_object.group(1), expand_term(rr_class.group(1), prefixes)))
    return projections


def patch_uc_table(full_name: str, class_iri: str, class_metadata: Dict[str, str]) -> None:
    payload = {
        "comment": class_metadata.get("comment") or class_metadata.get("label") or class_iri,
        "properties": {
            "semantic.class": class_iri,
            "semantic.label": class_metadata.get("label", ""),
            "semantic.source": "semantic-mapper",
        },
    }
    encoded_name = quote(full_name, safe="")
    url = f"{UNITY_CATALOG_API_URL}/tables/{encoded_name}"
    request = Request(url, data=json.dumps(payload).encode("utf-8"), method="PATCH", headers=uc_headers("application/json"))
    try:
        with urlopen(request, timeout=20) as response:
            print(f"Projected semantic metadata to UC table {full_name}: HTTP {response.status}")
    except HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        text = f"Unity Catalog projection failed for {full_name}: HTTP {exc.code} {message}"
        if STRICT_UC:
            raise RuntimeError(text) from exc
        print(f"WARNING: {text}")
    except (URLError, TimeoutError) as exc:
        text = f"Unity Catalog projection failed for {full_name}: {exc}"
        if STRICT_UC:
            raise RuntimeError(text) from exc
        print(f"WARNING: {text}")


def project_to_unity_catalog(ontology_files: List[Path], mapping_files: List[Path]) -> None:
    classes = parse_ontology_classes(ontology_files)
    projections = parse_mapping_projections(mapping_files)
    if not projections:
        print("No mapping projections found. Add dpa:unityCatalogObject to a TriplesMap to enable UC projection.")
        return
    print(f"Found {len(projections)} Unity Catalog projection target(s)")
    for full_name, class_iri in projections:
        metadata = classes.get(class_iri, {"label": class_iri, "comment": ""})
        patch_uc_table(full_name, class_iri, metadata)


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
