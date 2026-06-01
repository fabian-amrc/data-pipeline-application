# Semantic Mappings

Mappings align operational data to ontology terms. Prefer RML for files/object data and R2RML for relational sources.

Suggested layout:

```text
mappings/
|- rml/
|- r2rml/
`- sources/
```

Rules:

- Mappings reference ontology IRIs; they do not introduce authoritative semantics.
- Keep source identifiers explicit and reviewable.
- Version mapping changes with the ontology changes they depend on.
- Include small sample inputs for validation where possible.
