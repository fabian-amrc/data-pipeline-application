# Semantic Mapper

The semantic mapper owns the semantic source artefacts and mapper code for the data platform. It is the authoritative home for ontology/RDL, SHACL shapes, generated RML/R2RML mappings, and metadata projection into Unity Catalog.

Fuseki is deliberately separate: it is the triplestore runtime that stores and serves RDF. Unity Catalog is a projection target for operational metadata, not the semantic source of truth.

## Repository Layout

```text
semantic-mapper/
|- mapper/               # Sync job entrypoint and helper modules
|  `- lib/               # Encapsulated Fuseki, RDF, config, and UC projection code
|- ontology/             # Authoritative RDL/ontology modules
|- shapes/               # SHACL constraints for ontology and instance data
|- definitions/          # Python semantic declarations rendered to RML by the mapper
`- mappings/             # Optional hand-authored RML/R2RML mappings aligned to ontology terms
```


## Runtime Workflow

`semantic-mapper` deploys a GitOps-managed sync Job. On each Argo CD sync it:

1. Uploads ontology files to the Fuseki named graph `https://data-pipeline.local/graph/ontology`.
2. Uploads RML/R2RML mapping files to `https://data-pipeline.local/graph/mappings`.
3. Uploads SHACL shape files to `https://data-pipeline.local/graph/shapes`.
4. Imports Python semantic declarations, renders them to RML/R2RML Turtle, and includes that generated RML in the mappings graph.
5. Reads mapping projection annotations and writes derived comments/properties into Unity Catalog.

The current projection contract is intentionally narrow. Users declare table semantics with a small Python API instead of hand-authoring RML. The generated RML still opts into UC projection with `dpa:unityCatalogObject "catalog.schema.table"`, and the mapper projects metadata from the ontology class referenced by `rr:class`. Unity Catalog remains a projection target; the ontology and generated mappings remain authoritative runtime artifacts.

By default, Unity Catalog projection failures are logged as warnings so missing MVP tables do not block RDF graph publication. Set `STRICT_UNITY_CATALOG_PROJECTION=true` in the Job when failed UC writes should fail the sync.

## Python Semantic Declarations

Application authors should describe Spark-written datasets with `semantic_mapping.semantic_table` and `semantic_mapping.column`. The declaration is ordinary Python and is rendered by the mapper into RML before upload. For example:

```python
from semantic_mapping import column, semantic_table

EXAMPLE_DATASET_SEMANTICS = semantic_table(
    full_name="unity.default.example_dataset",
    class_iri="https://data-pipeline.local/ontology/Dataset",
    storage_location="s3://delta/example-dataset",
    source_uri="s3a://delta/example-dataset",
    subject_template="https://data-pipeline.local/resource/dataset/{id}",
    columns=[
        column("id", "INT", "Dataset identifier"),
        column("name", "STRING", "Display name"),
    ],
)

SEMANTIC_TABLES = [EXAMPLE_DATASET_SEMANTICS]
```

The semantic mapper imports modules that expose `SEMANTIC_TABLES`, renders them to RML, uploads the rendered RML to the mappings graph, and then uses the existing RML projection parser to instantiate Unity Catalog metadata.

## Ownership Boundaries

- Ontology/RDL owns business meaning, classes, properties, definitions, and controlled vocabulary alignment.
- Mappings own source-to-ontology alignment. They may reference MinIO paths, Spark tables, or source systems, but they do not define business meaning.
- The mapper projection code owns derived metadata writes into Unity Catalog.
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

## Fuseki Credentials

`manifests/fuseki-admin-secret.yaml` mirrors the Fuseki admin password into the `semantic-mapper` namespace for local development. Keep it in sync with `fuseki/manifests/fuseki-admin-secret.yaml`; replace both plaintext Secrets with Sealed Secrets, SOPS, External Secrets, or workload identity before using this pattern outside a local/dev cluster.
