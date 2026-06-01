# Semantic Mapper

The semantic mapper owns the semantic source artefacts and mapping/projection code for the data platform. It is the authoritative home for ontology/RDL, SHACL shapes, RML/R2RML mappings, and metadata projection into Unity Catalog.

Fuseki is deliberately separate: it is the triplestore runtime that stores and serves RDF. Unity Catalog is a projection target for operational metadata, not the semantic source of truth.

## Repository Layout

```text
semantic-mapper/
|- ontology/             # Authoritative RDL/ontology modules
|- shapes/               # SHACL constraints for ontology and instance data
|- mappings/             # RML/R2RML mappings aligned to ontology terms
`- projector/            # Metadata projection design and future implementation
```

## Ownership Boundaries

- Ontology/RDL owns business meaning, classes, properties, definitions, and controlled vocabulary alignment.
- Mappings own source-to-ontology alignment. They may reference MinIO paths, Spark tables, or source systems, but they do not define business meaning.
- The projector owns derived metadata writes into Unity Catalog.
- Fuseki owns RDF storage and SPARQL access for semantic artifacts and materialized RDF.
- Unity Catalog owns operational cataloguing, table permissions, and data access controls. It receives projected descriptions, comments, and tags.
- Spark owns data processing and materialization jobs. It consumes semantic configuration but is not the semantic source of truth.
- MinIO owns object storage only. Bucket and object paths are operational identifiers, not semantic definitions.

## Validation Workflow

Run validation before merging ontology or mapping changes:

1. Parse ontology, shapes, and mappings as RDF.
2. Run SHACL validation against ontology constraints and sample/materialized RDF.
3. Validate RML/R2RML mapping syntax and check that mapping predicates/classes resolve to ontology IRIs.
4. Generate a metadata projection diff for Unity Catalog and review it before applying.
5. Apply through GitOps after review.
