"""Shared API service state."""

from semantic_mapper.config import STATE_DIR
from semantic_mapper.storage import MappingStore


STORE = MappingStore(STATE_DIR)
