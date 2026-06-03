"""Python client DSL for registering semantic mappings.

Users describe datasets, subjects, and columns with ordinary Python objects.
The Semantic Mapper REST API turns those declarations into RML/Turtle,
validates them, stores them centrally, and can project metadata to Unity
Catalog.
"""

import json
import os
import urllib.error
import urllib.request
from pathlib import Path


class SemanticMapper:
    """Session scoped to one ontology and mapping profile."""

    def __init__(self, ontology: str = "", profile: str = "", base_url: str = ""):
        self.ontology = ontology or os.getenv("SEMANTIC_MAPPER_ONTOLOGY", "manufacturing-rdl")
        self.profile = profile or os.getenv("SEMANTIC_MAPPER_PROFILE", "spark-delta")
        self.base_url = (
            base_url
            or os.getenv("SEMANTIC_MAPPER_API_URL")
            or "http://semantic-mapper.semantic-mapper.svc.cluster.local:8080"
        ).rstrip("/")

    def dataset(self, name: str):
        """Begin a semantic mapping definition for a dataset or table."""

        return DatasetMapping(self, name)

    def register_rml(self, ttl: str):
        """Register expert-authored RML/Turtle directly."""

        return self._request("/mappings/rml", {"ontology": self.ontology, "profile": self.profile, "ttl": ttl})

    def register_rml_file(self, path: str):
        """Register expert-authored RML/Turtle from a local file."""

        return self.register_rml(Path(path).read_text(encoding="utf-8"))

    def validate_mapping(self, mapping):
        """Validate a registered mapping by id or response payload."""

        return self._request(f"/mappings/{mapping_id(mapping)}/validate", {})

    def activate_mapping(self, mapping):
        """Activate a registered mapping and publish active RML to Fuseki."""

        return self._request(f"/mappings/{mapping_id(mapping)}/activate", {})

    def project_unity_catalog(self, mapping):
        """Project one registered mapping into Unity Catalog metadata."""

        return self._request(f"/mappings/{mapping_id(mapping)}/project/unity-catalog", {})

    def _request(self, path: str, payload: dict):
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Semantic Mapper API {exc.code} for {path}: {body}") from exc


class DatasetMapping:
    """Mutable builder for one dataset mapping declaration."""

    def __init__(self, mapper: SemanticMapper, name: str):
        self.mapper = mapper
        self.name = name
        self._row_subject = {}
        self._subject_identifier = {}
        self._storage = {}
        self._columns = []

    def row_subject(self, *, rdf_class: str, label: str = ""):
        """Define the ontology class represented by each dataset row."""

        self._row_subject = {"rdf_class": rdf_class, "label": label}
        return self

    def subject_identifier(self, *, column: str, scheme: str):
        """Declare that a column identifies the row subject with a named scheme."""

        self._subject_identifier = {"column": column, "scheme": scheme}
        return self

    def storage(self, *, source_uri: str, storage_location: str = ""):
        """Set the physical source URI and optional UC external storage location."""

        self._storage = {"source_uri": source_uri, "storage_location": storage_location}
        return self

    def column(self, name: str, type_name: str = "STRING", comment: str = ""):
        """Select a column for semantic mapping."""

        return ColumnMapping(self, name, type_name, comment)

    def register(self):
        """Submit this mapping definition to the Semantic Mapper API."""

        return self.mapper._request("/mappings", self.to_payload())

    def register_and_project(self):
        """Register, validate, activate, and project this mapping."""

        mapping = self.register()
        validation = self.mapper.validate_mapping(mapping)
        activated = self.mapper.activate_mapping(mapping)
        projection = self.mapper.project_unity_catalog(mapping)
        return {"mapping": activated, "validation": validation, "projection": projection}

    def to_payload(self):
        """Return the JSON payload consumed by `POST /mappings`."""

        return {
            "ontology": self.mapper.ontology,
            "profile": self.mapper.profile,
            "dataset": {
                "name": self.name,
                "row_subject": self._row_subject,
                "subject_identifier": self._subject_identifier,
                **self._storage,
                "columns": self._columns,
            },
        }

    def _add_column(self, column):
        self._columns.append(column)
        return self


class ColumnMapping:
    """Builder for one mapped dataset column."""

    def __init__(self, dataset: DatasetMapping, name: str, type_name: str, comment: str):
        self.dataset = dataset
        self.name = name
        self.type_name = type_name
        self.comment = comment

    def literal(self, *, predicate: str, datatype: str = "", language: str = ""):
        """Map this column to an RDF literal property."""

        return self.dataset._add_column(self._base("literal", predicate=predicate, datatype=datatype, language=language))

    def entity_reference(self, *, scheme: str, predicate: str):
        """Map this column to another entity through an identifier scheme."""

        return self.dataset._add_column(self._base("entity_reference", scheme=scheme, predicate=predicate))

    def classification(self, *, term: str, predicate: str = ""):
        """Associate this column with a semantic category or classification."""

        return self.dataset._add_column(self._base("classification", term=term, predicate=predicate))

    def ignore(self):
        """Explicitly mark this column as unmapped."""

        return self.dataset._add_column(self._base("ignore"))

    def _base(self, kind: str, **extra):
        return {"name": self.name, "type_name": self.type_name, "comment": self.comment, "kind": kind, **extra}


def mapping_id(mapping):
    """Return a mapping id from a raw id string or API response payload."""

    if isinstance(mapping, str):
        return mapping
    if isinstance(mapping, dict) and mapping.get("id"):
        return str(mapping["id"])
    raise ValueError(f"Mapping id is required, got {mapping!r}")
