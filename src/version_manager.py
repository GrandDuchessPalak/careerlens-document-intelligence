from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List

from config import get_settings

logger = logging.getLogger(__name__)

VERSION_PATTERN = re.compile(r"^v(\d+)$")


def next_version(doc_id: str) -> str:
    """Returns the next version string (v1, v2, ...) for a given doc_id."""
    settings = get_settings()
    doc_dir = Path(settings.docs_dir) / doc_id

    if not doc_dir.exists():
        return "v1"

    existing = [
        int(m.group(1))
        for p in doc_dir.iterdir()
        if p.is_dir() and (m := VERSION_PATTERN.match(p.name))
    ]
    return f"v{max(existing) + 1}" if existing else "v1"


def list_versions(doc_id: str) -> List[str]:
    settings = get_settings()
    doc_dir = Path(settings.docs_dir) / doc_id

    if not doc_dir.exists():
        return []

    versions = [
        p.name for p in doc_dir.iterdir()
        if p.is_dir() and VERSION_PATTERN.match(p.name)
    ]
    return sorted(versions, key=lambda v: int(v[1:]))


def latest_version(doc_id: str) -> str | None:
    versions = list_versions(doc_id)
    return versions[-1] if versions else None