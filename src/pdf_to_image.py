"""
pdf_to_image.py

Converts an uploaded document (PDF or image file) into a list of PIL
Images ready for the extraction pipeline. This is the first stage of
the pipeline (upload -> preprocessing -> classification -> extraction).

Enhancement here is intentionally minimal. Donut and LayoutLMv3 are
trained on fairly natural document images, and aggressive filtering
(heavy sharpening, thresholding, contrast stretching) tends to hurt
them rather than help — see the gotchas note in the project design
doc. If a specific failure mode later genuinely needs more aggressive
preprocessing, add it as an explicit separate step; don't fold it into
this default path.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from PIL import Image, ImageOps
from pdf2image import convert_from_path
from pdf2image.exceptions import (
    PDFInfoNotInstalledError,
    PDFPageCountError,
    PDFSyntaxError,
)

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}
SUPPORTED_PDF_EXTENSIONS = {".pdf"}

DEFAULT_DPI = 200
# Cap the longer side of any page/image. Protects against huge phone
# scans blowing up memory/inference time; we only ever downscale, never
# upscale a smaller image.
MAX_IMAGE_SIDE = 2000


class UnsupportedFileTypeError(ValueError):
    """Raised when a file extension isn't a supported PDF or image type."""


class PopplerNotInstalledError(RuntimeError):
    """
    Raised when the poppler system dependency is missing. This is NOT a
    pip package — it must be installed at the OS level:
      Linux:   apt install poppler-utils
      macOS:   brew install poppler
      Windows: download poppler binaries and add them to PATH
    """


def load_document_images(file_path: Path) -> List[Image.Image]:
    """
    Load a document (PDF or single image file) as a list of normalized
    PIL Images. A multi-page PDF yields one image per page; a plain
    image file always yields exactly one.
    """
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if suffix in SUPPORTED_PDF_EXTENSIONS:
        images = _pdf_to_images(file_path)
    elif suffix in SUPPORTED_IMAGE_EXTENSIONS:
        images = [Image.open(file_path)]
    else:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{suffix}' for {file_path.name}. "
            f"Supported: {sorted(SUPPORTED_PDF_EXTENSIONS | SUPPORTED_IMAGE_EXTENSIONS)}"
        )

    return [_normalize_image(image) for image in images]


def _pdf_to_images(pdf_path: Path, dpi: int = DEFAULT_DPI) -> List[Image.Image]:
    """Convert every page of a PDF into a PIL Image."""
    try:
        return convert_from_path(str(pdf_path), dpi=dpi)
    except PDFInfoNotInstalledError as exc:
        raise PopplerNotInstalledError(
            "poppler is not installed or not on PATH — this is a system "
            "dependency, not a pip package. See PopplerNotInstalledError's "
            "docstring for install instructions."
        ) from exc
    except (PDFPageCountError, PDFSyntaxError) as exc:
        logger.error("Failed to read PDF %s: %s", pdf_path, exc)
        raise


def _normalize_image(image: Image.Image) -> Image.Image:
    """
    Minimal, deliberately gentle normalization:
    - auto-orient using EXIF data if present (common with phone-scanned
      certificates that come in sideways/upside down)
    - convert to RGB (some scans arrive as CMYK/grayscale/palette mode,
      which some models choke on)
    - downscale only if unusually large; never upscale, never
      sharpen/threshold/denoise
    """
    image = ImageOps.exif_transpose(image)

    if image.mode != "RGB":
        image = image.convert("RGB")

    longer_side = max(image.size)
    if longer_side > MAX_IMAGE_SIDE:
        scale = MAX_IMAGE_SIDE / longer_side
        new_size = (int(image.width * scale), int(image.height * scale))
        old_size = image.size
        image = image.resize(new_size, Image.LANCZOS)
        logger.debug("Downscaled image from %s to %s", old_size, new_size)
    return image