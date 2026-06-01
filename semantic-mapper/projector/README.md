# Metadata Projector

The metadata projector reads ontology and mapping artifacts and writes derived metadata into Unity Catalog. Unity Catalog is a projection target, not the semantic source of truth.

## MVP Design

Input:

- Ontology/RDL Turtle files from `semantic-mapper/ontology`.
- Mapping files from `semantic-mapper/mappings`.
- Optional projection rules that map ontology annotations to Unity Catalog fields.

Output:

- Unity Catalog catalog/schema/table comments.
- Tags or properties representing semantic identifiers and classification.

Processing model:

1. Parse ontology and mappings with an RDF library.
2. Resolve the semantic entity for each operational UC object.
3. Build a desired-state metadata document.
4. Diff desired state against Unity Catalog.
5. Apply comments/tags through the Unity Catalog API.

Deployment model:

- Start as a manually triggered Kubernetes Job.
- Promote to CronJob only when projection is stable and idempotent.
- Mount semantic artifacts from a ConfigMap for small MVP content, or read from Git/object storage later.

Important behavior:

- Never infer semantic truth from Unity Catalog metadata.
- Projection should be idempotent.
- Projection should label managed fields so manual UC-only metadata can be identified and eventually rejected.
