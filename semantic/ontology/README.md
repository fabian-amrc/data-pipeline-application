# Ontology / RDL

Ontology files here are the semantic source of truth. Organize modules by domain, and keep stable IRIs even when file layout changes.

Suggested layout:

```text
ontology/
|- core.ttl              # Shared classes/properties
|- datasets.ttl          # Dataset/table semantics
|- business/             # Domain modules
`- imports/              # External vocabularies when vendoring is required
```

Authoring rules:

- Prefer Turtle for reviewability.
- Use resolvable, stable IRIs.
- Put human-readable definitions in `rdfs:comment` or `skos:definition`.
- Use explicit ownership metadata such as `dcterms:creator` or `prov:wasAttributedTo` where useful.
