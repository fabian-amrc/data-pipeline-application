# Semantic Mappings

Mappings are now registered through the Semantic Mapper REST API.

Use the Python DSL for normal Spark/data-asset mappings. The API generates RML/Turtle, validates it, stores it, and uploads active mappings to the mappings graph.

Use this directory only for optional hand-authored RML/Turtle examples or fixtures that cannot be expressed through the minimal Python API. Expert-authored RML should be registered with `POST /mappings/rml` or `SemanticMapper.register_rml_file(...)`.
