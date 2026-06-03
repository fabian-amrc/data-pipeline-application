
"""Server-side RML generation for Semantic Mapper API payloads."""

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List


DPA_PREFIX = "https://data-pipeline.local/ontology/"
RR_PREFIX = "http://www.w3.org/ns/r2rml#"
RML_PREFIX = "http://semweb.mmlab.be/ns/rml#"
XSD_PREFIX = "http://www.w3.org/2001/XMLSchema#"
RML_REFERENCE_FORMULATION = "http://semweb.mmlab.be/ns/ql#CSV"


@dataclass(frozen=True)
class IdentifierScheme:
    """Named identifier scheme with a URI template hidden from API users."""

    id: str
    label: str
    template: str

    def subject_template(self, column: str) -> str:
        """Return an RML row-subject template for a source column."""

        return self.template.replace("{value}", "{" + column + "}")

    def reference_template(self, column: str) -> str:
        """Return an RML object template for an entity reference column."""

        return self.subject_template(column)


def generate_rml(mapping_id: str, payload: Dict[str, object], schemes: Dict[str, IdentifierScheme]) -> str:
    """Generate RML/Turtle from the simple mapping JSON payload."""

    dataset = payload.get("dataset") or {}
    name = str(dataset.get("name") or "").strip()
    if not name:
        raise ValueError("dataset.name is required")

    row_subject = dataset.get("row_subject") or {}
    rdf_class = expand_curie(str(row_subject.get("rdf_class") or "dpa:Dataset"))
    subject_identifier = dataset.get("subject_identifier") or {}
    subject_column = str(subject_identifier.get("column") or "").strip()
    scheme_id = str(subject_identifier.get("scheme") or "").strip()
    if not subject_column or not scheme_id:
        raise ValueError("dataset.subject_identifier requires column and scheme")
    if scheme_id not in schemes:
        raise ValueError(f"Unknown identifier scheme: {scheme_id}")

    storage_location = str(dataset.get("storage_location") or f"s3://{name.replace('.', '/')}")
    source_uri = str(dataset.get("source_uri") or storage_location.replace("s3://", "s3a://", 1))
    mapping_name = safe_mapping_name(mapping_id)
    lines = [
        f"@prefix dpa: <{DPA_PREFIX}> .",
        f"@prefix rr: <{RR_PREFIX}> .",
        f"@prefix rml: <{RML_PREFIX}> .",
        f"@prefix xsd: <{XSD_PREFIX}> .",
        "",
        f"<{mapping_name}>",
        "    a rr:TriplesMap ;",
        f"    dpa:unityCatalogObject \"{escape_literal(name)}\" ;",
        f"    dpa:unityCatalogStorageLocation \"{escape_literal(storage_location)}\" ;",
    ]

    mapped_columns = [column for column in dataset.get("columns") or [] if column.get("kind") != "ignore"]
    for column in mapped_columns:
        annotation = column_annotation(column)
        lines.append(f"    dpa:unityCatalogColumn \"{escape_literal(annotation)}\" ;")

    lines.extend(
        [
            "    rml:logicalSource [",
            f"        rml:source \"{escape_literal(source_uri)}\" ;",
            f"        rml:referenceFormulation <{RML_REFERENCE_FORMULATION}>",
            "    ] ;",
            "    rr:subjectMap [",
            f"        rr:template \"{escape_literal(schemes[scheme_id].subject_template(subject_column))}\" ;",
            f"        rr:class <{rdf_class}>",
            "    ]",
        ]
    )

    predicate_maps = [render_predicate_object(column, schemes) for column in mapped_columns]
    predicate_maps = [item for item in predicate_maps if item]
    if predicate_maps:
        lines[-1] += " ;"
        for index, item in enumerate(predicate_maps):
            suffix = " ." if index == len(predicate_maps) - 1 else " ;"
            lines.extend(indent_block(item, 4, first=f"rr:predicateObjectMap [", suffix=suffix))
    else:
        lines[-1] += " ."
    lines.append("")
    return "\n".join(lines)


def render_predicate_object(column: Dict[str, object], schemes: Dict[str, IdentifierScheme]) -> List[str]:
    """Render one column mapping as an RML predicate-object map."""

    kind = column.get("kind")
    name = str(column.get("name") or "")
    raw_predicate = str(column.get("predicate") or "")
    predicate = expand_curie(raw_predicate) if raw_predicate else ""
    if kind == "literal":
        if not predicate:
            raise ValueError(f"Column {name} literal mapping requires predicate")
        datatype = expand_curie(str(column.get("datatype") or default_xsd_type(str(column.get("type_name") or "STRING"))))
        return [
            f"rr:predicate <{predicate}> ;",
            "rr:objectMap [",
            f"    rml:reference \"{escape_literal(name)}\" ;",
            f"    rr:datatype <{datatype}>",
            "]",
        ]
    if kind == "entity_reference":
        scheme_id = str(column.get("scheme") or "")
        if not predicate:
            raise ValueError(f"Column {name} entity reference mapping requires predicate")
        if scheme_id not in schemes:
            raise ValueError(f"Unknown identifier scheme: {scheme_id}")
        return [
            f"rr:predicate <{predicate}> ;",
            "rr:objectMap [",
            f"    rr:template \"{escape_literal(schemes[scheme_id].reference_template(name))}\"",
            "]",
        ]
    if kind == "classification":
        term = expand_curie(str(column.get("term") or ""))
        classification_predicate = predicate if raw_predicate else f"{DPA_PREFIX}classifiedAs"
        return [
            f"rr:predicate <{classification_predicate}> ;",
            f"rr:object <{term}>",
        ]
    return []


def column_annotation(column: Dict[str, object]) -> str:
    """Return the compact UC column annotation for a mapped column."""

    name = str(column.get("name") or "")
    type_name = str(column.get("type_name") or "STRING").upper()
    comment = str(column.get("comment") or "")
    return ":".join(part for part in [name, type_name, comment] if part)


def default_xsd_type(type_name: str) -> str:
    """Map common Spark/UC type names to XSD datatype IRIs."""

    return {
        "BOOLEAN": f"{XSD_PREFIX}boolean",
        "BYTE": f"{XSD_PREFIX}byte",
        "SHORT": f"{XSD_PREFIX}short",
        "INT": f"{XSD_PREFIX}integer",
        "INTEGER": f"{XSD_PREFIX}integer",
        "LONG": f"{XSD_PREFIX}long",
        "FLOAT": f"{XSD_PREFIX}float",
        "DOUBLE": f"{XSD_PREFIX}double",
        "DATE": f"{XSD_PREFIX}date",
        "TIMESTAMP": f"{XSD_PREFIX}dateTime",
        "STRING": f"{XSD_PREFIX}string",
    }.get(type_name.upper(), f"{XSD_PREFIX}string")


def expand_curie(value: str) -> str:
    """Expand a small set of built-in CURIE prefixes used by mapper payloads."""

    if value.startswith("http://") or value.startswith("https://"):
        return value
    if value.startswith("dpa:"):
        return DPA_PREFIX + value.split(":", 1)[1]
    if value.startswith("xsd:"):
        return XSD_PREFIX + value.split(":", 1)[1]
    if ":" in value:
        prefix, local = value.split(":", 1)
        return f"https://data-pipeline.local/ontology/{prefix}/{local}"
    return DPA_PREFIX + value


def safe_mapping_name(mapping_id: str) -> str:
    """Create a local IRI fragment from a mapping identifier."""

    return re.sub(r"[^A-Za-z0-9_-]", "-", mapping_id)


def escape_literal(value: str) -> str:
    """Escape a value for a generated Turtle string literal."""

    return value.replace("\\", "\\\\").replace('"', '\\"')


def indent_block(lines: Iterable[str], spaces: int, first: str, suffix: str) -> List[str]:
    """Indent an RML nested block with a custom opening and closing suffix."""

    lines = list(lines)
    padding = " " * spaces
    result = [padding + first]
    result.extend(padding + "    " + line for line in lines)
    result.append(padding + "]" + suffix)
    return result
