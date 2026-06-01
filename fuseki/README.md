# Fuseki

This directory owns the Apache Jena Fuseki triplestore runtime implementation. It is a deployable Argo CD/Kustomize application and contains the Kubernetes manifests, persistent storage, service definition, and Fuseki assembler configuration.

Semantic source artefacts live in `semantic-mapper/`. Fuseki stores and serves RDF; it does not own the ontology, SHACL shapes, RML/R2RML mappings, or Unity Catalog projection logic.

## Layout

```text
fuseki/
|- app.yaml              # Argo CD Application
|- kustomization.yaml    # Kustomize root for the runtime
|- config/config.ttl     # Fuseki assembler configuration
`- manifests/            # Namespace, PVC, Deployment, Service
```
