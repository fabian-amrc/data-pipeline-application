"""Lightweight Turtle parsers for semantic mapper projection metadata.

The mapper only needs a narrow subset of RDF/Turtle syntax: prefixes, ontology
class labels/comments, and RML triples-map annotations that describe Unity
Catalog projection targets. These helpers keep that extraction dependency-free.
"""

import json
import re
from pathlib import Path
from typing import Dict, Iterable, List

from lib.semantic_files import read_all


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


def parse_prefixes(text: str) -> Dict[str, str]:
    """Extract Turtle `@prefix` declarations as prefix-to-IRI mappings."""

    return dict(PREFIX_RE.findall(text))


def expand_term(term: str, prefixes: Dict[str, str]) -> str:
    """Expand an RDF term from QName or angle-bracket form into an IRI."""

    term = term.strip()
    if term.startswith("<") and term.endswith(">"):
        return term[1:-1]
    if ":" in term:
        prefix, local = term.split(":", 1)
        if prefix in prefixes:
            return prefixes[prefix] + local
    return term


def statements(text: str) -> Iterable[str]:
    """Yield simple Turtle statements by accumulating lines until a period."""

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
    """Return ontology class metadata keyed by expanded class IRI."""

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
    """Parse `dpa:unityCatalogColumn` annotations into UC column payloads."""

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
    """Extract Unity Catalog projection targets from RML mapping files."""

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
