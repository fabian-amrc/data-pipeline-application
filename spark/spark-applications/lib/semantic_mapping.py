"""Small Python API for declaring semantic mappings from Spark applications.

Spark jobs use this module to describe the semantic meaning of the data they
write without asking job authors to hand-write RML/R2RML. The semantic mapper
imports these declarations, renders RML Turtle, uploads that RML to the mappings
graph, and projects the corresponding Unity Catalog metadata.
"""

from dataclasses import dataclass
from typing import Iterable, List


DPA_PREFIX = "https://data-pipeline.local/ontology/"
RML_REFERENCE_FORMULATION = "http://semweb.mmlab.be/ns/ql#CSV"


@dataclass(frozen=True)
class SemanticColumn:
    """Column metadata that can be rendered as a UC projection annotation."""

    name: str
    type_name: str
    comment: str = ""

    def to_annotation(self) -> str:
        """Render the compact `name:type[:comment]` annotation value."""

        parts = [self.name, self.type_name.upper()]
        if self.comment:
            parts.append(self.comment)
        return ":".join(parts)


@dataclass(frozen=True)
class SemanticTable:
    """Semantic declaration for one Spark-written table or dataset."""

    full_name: str
    class_iri: str
    storage_location: str
    source_uri: str
    subject_template: str
    columns: List[SemanticColumn]
    mapping_id: str = "DatasetMapping"

    def to_rml(self) -> str:
        """Render this declaration as the RML Turtle consumed by semantic-mapper."""

        if len(self.full_name.split(".")) != 3:
            raise ValueError(f"Unity Catalog table name must be catalog.schema.table: {self.full_name}")
        if not self.columns:
            raise ValueError(f"Semantic table {self.full_name} requires at least one column")

        lines = [
            f"@prefix dpa: <{DPA_PREFIX}> .",
            "@prefix rr: <http://www.w3.org/ns/r2rml#> .",
            "@prefix rml: <http://semweb.mmlab.be/ns/rml#> .",
            "",
            f"<{_escape_iri_fragment(self.mapping_id)}>",
            "    a rr:TriplesMap ;",
            f"    dpa:unityCatalogObject \"{_escape_literal(self.full_name)}\" ;",
            f"    dpa:unityCatalogStorageLocation \"{_escape_literal(self.storage_location)}\" ;",
        ]
        lines.extend(
            f"    dpa:unityCatalogColumn \"{_escape_literal(column.to_annotation())}\" ;"
            for column in self.columns
        )
        lines.extend(
            [
                "    rml:logicalSource [",
                f"        rml:source \"{_escape_literal(self.source_uri)}\" ;",
                f"        rml:referenceFormulation <{RML_REFERENCE_FORMULATION}>",
                "    ] ;",
                "    rr:subjectMap [",
                f"        rr:template \"{_escape_literal(self.subject_template)}\" ;",
                f"        rr:class <{self.class_iri}>",
                "    ] .",
                "",
            ]
        )
        return "\n".join(lines)


def column(name: str, type_name: str, comment: str = "") -> SemanticColumn:
    """Create a semantic column declaration with a UC/Spark SQL type name."""

    return SemanticColumn(name=name, type_name=type_name, comment=comment)


def semantic_table(
    *,
    full_name: str,
    class_iri: str,
    storage_location: str,
    source_uri: str,
    subject_template: str,
    columns: Iterable[SemanticColumn],
    mapping_id: str = "DatasetMapping",
) -> SemanticTable:
    """Create a semantic table declaration from ordinary Python values."""

    return SemanticTable(
        full_name=full_name,
        class_iri=class_iri,
        storage_location=storage_location,
        source_uri=source_uri,
        subject_template=subject_template,
        columns=list(columns),
        mapping_id=mapping_id,
    )


def render_rml(tables: Iterable[SemanticTable]) -> str:
    """Render one or more semantic table declarations into RML Turtle."""

    return "\n".join(table.to_rml().strip() for table in tables).strip() + "\n"


def _escape_literal(value: str) -> str:
    """Escape a small Turtle string literal used by generated annotations."""

    return value.replace("\\", "\\\\").replace('"', '\\"')


def _escape_iri_fragment(value: str) -> str:
    """Escape angle brackets in local mapping identifiers."""

    return value.replace("<", "%3C").replace(">", "%3E")
