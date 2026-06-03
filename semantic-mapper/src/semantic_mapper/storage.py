
"""Filesystem-backed storage for Semantic Mapper mappings and RML."""

import json
import uuid
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, Iterable, List, Optional


class MappingStore:
    """Persist mapping metadata and RML payloads under a state directory."""

    def __init__(self, root: Path):
        self.root = root
        self.mappings_dir = root / "mappings"
        self.jobs_dir = root / "projection-jobs"
        self.mappings_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def create_mapping(self, *, source: str, ontology: str, profile: str, rml: str, payload=None, status: str = "draft") -> Dict[str, object]:
        """Create a mapping record and write its RML document."""

        mapping_id = f"map-{uuid.uuid4().hex[:12]}"
        now = timestamp()
        metadata = {
            "id": mapping_id,
            "source": source,
            "ontology": ontology,
            "profile": profile,
            "status": status,
            "created_at": now,
            "updated_at": now,
            "payload": payload or {},
        }
        self._write_record(mapping_id, metadata, rml)
        return metadata

    def list_mappings(self, *, dataset_id: Optional[str] = None) -> List[Dict[str, object]]:
        """Return stored mapping records, optionally filtered by dataset name."""

        records = [self.get_mapping(path.name) for path in sorted(self.mappings_dir.iterdir()) if path.is_dir()]
        records = [record for record in records if record]
        if dataset_id:
            records = [record for record in records if dataset_name(record) == dataset_id]
        return records

    def get_mapping(self, mapping_id: str) -> Optional[Dict[str, object]]:
        """Return one mapping record or None when it is absent."""

        path = self._metadata_path(mapping_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def get_rml(self, mapping_id: str) -> Optional[str]:
        """Return the RML for one mapping or None when absent."""

        path = self._rml_path(mapping_id)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def update_rml(self, mapping_id: str, rml: str) -> Dict[str, object]:
        """Replace a mapping RML document and mark it as updated."""

        metadata = self.require_mapping(mapping_id)
        metadata["updated_at"] = timestamp()
        metadata["source"] = "rml"
        self._write_record(mapping_id, metadata, rml)
        return metadata

    def set_status(self, mapping_id: str, status: str) -> Dict[str, object]:
        """Update a mapping lifecycle status."""

        metadata = self.require_mapping(mapping_id)
        metadata["status"] = status
        metadata["updated_at"] = timestamp()
        self._metadata_path(mapping_id).write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
        return metadata

    def delete_mapping(self, mapping_id: str) -> None:
        """Delete a mapping record and its RML file if present."""

        directory = self.mappings_dir / mapping_id
        if directory.exists():
            for path in directory.iterdir():
                path.unlink()
            directory.rmdir()

    def active_rml_files(self) -> List[Path]:
        """Return RML paths for active mappings."""

        files = []
        for record in self.list_mappings():
            if record.get("status") == "active":
                files.append(self._rml_path(str(record["id"])))
        return files

    def rml_files(self, mapping_ids: Iterable[str]) -> List[Path]:
        """Return RML paths for specific mapping ids."""

        return [self._rml_path(mapping_id) for mapping_id in mapping_ids]

    def create_projection_job(self, payload: Dict[str, object]) -> Dict[str, object]:
        """Persist a completed projection job record."""

        job_id = f"job-{uuid.uuid4().hex[:12]}"
        record = {"id": job_id, "status": "succeeded", "created_at": timestamp(), **payload}
        (self.jobs_dir / f"{job_id}.json").write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
        return record

    def get_projection_job(self, job_id: str) -> Optional[Dict[str, object]]:
        """Return a projection job record by id."""

        path = self.jobs_dir / f"{job_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def require_mapping(self, mapping_id: str) -> Dict[str, object]:
        """Return a mapping or raise KeyError when it does not exist."""

        mapping = self.get_mapping(mapping_id)
        if not mapping:
            raise KeyError(mapping_id)
        return mapping

    def _write_record(self, mapping_id: str, metadata: Dict[str, object], rml: str) -> None:
        directory = self.mappings_dir / mapping_id
        directory.mkdir(parents=True, exist_ok=True)
        self._metadata_path(mapping_id).write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
        self._rml_path(mapping_id).write_text(rml, encoding="utf-8")

    def _metadata_path(self, mapping_id: str) -> Path:
        return self.mappings_dir / mapping_id / "metadata.json"

    def _rml_path(self, mapping_id: str) -> Path:
        return self.mappings_dir / mapping_id / "mapping.rml.ttl"


def timestamp() -> str:
    """Return an ISO timestamp in UTC."""

    return datetime.now(UTC).isoformat()


def dataset_name(record: Dict[str, object]) -> str:
    """Return the dataset name embedded in a simple mapping payload."""

    payload = record.get("payload") or {}
    dataset = payload.get("dataset") or {}
    return str(dataset.get("name") or "")
