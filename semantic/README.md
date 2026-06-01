# Semantic Layer

The semantic layer is the authoritative source for ontology/RDL, SHACL shapes, and semantic mappings. Unity Catalog remains an operational catalog and access-control surface; semantic metadata is projected into it from this layer, not authored there.

## Repository Layout

```text
semantic/
|- ontology/             # Authoritative RDL/ontology modules
|- shapes/               # SHACL constraints for ontology and instance data
|- mappings/             # RML/R2RML mappings aligned to ontology terms
|- fuseki/               # Kustomize-managed Apache Jena Fuseki runtime
`- projector/            # Metadata projection design and future implementation
```

## Ownership Boundaries

- Ontology/RDL owns business meaning, classes, properties, definitions, and controlled vocabulary alignment.
- Mappings own source-to-ontology alignment. They may reference MinIO paths, Spark tables, or source systems, but they do not define business meaning.
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

## MVP Plan

1. Deploy internal Fuseki with a persistent dataset named `semantic`.
2. Commit initial ontology, SHACL, and mapping skeletons.
3. Add CI validation for RDF parseability and SHACL shape checks.
4. Build a metadata projector as a Kubernetes Job or CronJob that reads semantic artifacts and updates Unity Catalog comments/tags.
5. Add RDF materialization jobs later, using Spark or a lightweight RML processor.

## Risks and Simplifications

- The MVP Fuseki service is internal-only. Add authentication before exposing it through Traefik.
- Do not edit semantic metadata directly in Unity Catalog. Treat UC metadata as a projection cache.
- Keep mappings in Git and version them with ontology changes to avoid semantic drift.
- Avoid adopting a larger semantic platform until SPARQL/query workload justifies it.
- For now, project only comments, descriptions, and tags into Unity Catalog.
