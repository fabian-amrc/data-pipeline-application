# Semantic Mappings

This directory is reserved for optional hand-authored RML/R2RML mappings. The preferred path for Spark-authored datasets is to declare semantics in Python with `semantic_mapping.semantic_table`; the semantic mapper renders those declarations to RML and uploads the generated Turtle to the mappings graph.

Keep hand-authored RML here only when a mapping cannot be expressed with the minimal Python declaration API.
