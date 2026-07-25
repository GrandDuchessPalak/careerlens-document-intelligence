from __future__ import annotations

import logging
import sys
from pathlib import Path

from PIL import Image


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def image_to_bytes(image: Image.Image, fmt: str = "PNG") -> bytes:
    from io import BytesIO
    buf = BytesIO()
    image.save(buf, format=fmt)
    return buf.getvalue()


def safe_get(d: dict, *keys, default=None):
    """Nested dict.get with a fallback, e.g. safe_get(data, 'a', 'b')."""
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return d