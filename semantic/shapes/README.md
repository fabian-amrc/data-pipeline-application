# SHACL Shapes

Use SHACL to validate ontology quality and materialized RDF. Keep shapes close to the ontology concepts they constrain, and separate authoring checks from data-quality checks.

Suggested layout:

```text
shapes/
|- ontology-quality.shacl.ttl
`- data-quality/
```
