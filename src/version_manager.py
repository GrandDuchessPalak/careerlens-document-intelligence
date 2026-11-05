"""Versioning: every upload of the same doc_id creates the next version; nothing is overwritten."""
from typing import Optional

from .storage import Storage


class VersionManager:
    def __init__(self, storage: Storage):
        self.storage = storage

    def next_version(self, doc_id: str) -> int:
        versions = self.storage.list_versions(doc_id)
        return (versions[-1] + 1) if versions else 1

    def resolve(self, doc_id: str, version: Optional[int] = None) -> int:
        """Return `version`, or the latest version when None. Raises FileNotFoundError if unknown."""
        versions = self.storage.list_versions(doc_id)
        if not versions:
            raise FileNotFoundError(f"Unknown document: {doc_id}")
        if version is None:
            return versions[-1]
        if version not in versions:
            raise FileNotFoundError(f"{doc_id} has no version {version}")
        return version
