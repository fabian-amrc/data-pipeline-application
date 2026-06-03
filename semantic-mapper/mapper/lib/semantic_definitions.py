"""Load Spark-authored semantic declarations and render them as RML."""

import importlib.util
import sys
from pathlib import Path
from typing import Iterable, List

SEMANTIC_MAPPING_DIR = Path(__file__).parent
if str(SEMANTIC_MAPPING_DIR) not in sys.path:
    sys.path.insert(0, str(SEMANTIC_MAPPING_DIR))

from semantic_mapping import SemanticTable, render_rml


def load_semantic_tables(directory: Path) -> List[SemanticTable]:
    """Import declaration modules and collect their `SEMANTIC_TABLES` values."""

    tables: List[SemanticTable] = []
    if not directory.exists():
        return tables

    for path in sorted(directory.glob("*.py")):
        module = _load_module(path)
        declared = getattr(module, "SEMANTIC_TABLES", [])
        if isinstance(declared, SemanticTable):
            tables.append(declared)
        else:
            tables.extend(declared)
    return tables


def write_generated_rml(tables: Iterable[SemanticTable], output_file: Path) -> List[Path]:
    """Render semantic table declarations to an RML file and return it if non-empty."""

    tables = list(tables)
    if not tables:
        return []

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(render_rml(tables), encoding="utf-8")
    return [output_file]


def _load_module(path: Path):
    """Load one declaration module from an explicit filesystem path."""

    module_name = f"semantic_declaration_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load semantic declaration module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
