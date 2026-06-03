"""File loading helpers for semantic mapper Turtle sources."""

from pathlib import Path
from typing import Iterable, List


def ttl_files(directory: Path) -> List[Path]:
    """Return visible `.ttl` files under a directory in stable order."""

    return sorted(
        path
        for path in directory.rglob("*.ttl")
        if path.is_file() and not any(part.startswith("..") for part in path.parts)
    )


def read_all(files: Iterable[Path]) -> str:
    """Concatenate source files with lightweight source markers for debugging."""

    chunks = []
    for file in files:
        chunks.append(f"# Source: {file.name}\n")
        chunks.append(file.read_text(encoding="utf-8"))
        chunks.append("\n")
    return "".join(chunks)
