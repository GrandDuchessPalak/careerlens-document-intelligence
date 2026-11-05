from pathlib import Path
from typing import List

from PIL import Image, ImageOps

import config

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"}


def pdf_to_images(path, dpi: int = config.PDF_DPI, max_pages: int = config.MAX_PAGES) -> List[Image.Image]:
    from pdf2image import convert_from_path
    from pdf2image.exceptions import PDFInfoNotInstalledError
    try:
        return convert_from_path(str(path), dpi=dpi, first_page=1, last_page=max_pages)
    except PDFInfoNotInstalledError as e:
        raise RuntimeError(
            "poppler is not installed. Linux: apt install poppler-utils | macOS: brew install poppler | "
            "Windows: install the poppler binaries and add their /bin folder to PATH") from e


def enhance(img: Image.Image, max_side: int = config.MAX_IMAGE_SIDE) -> Image.Image:
    """Deliberately minimal: fix EXIF rotation, force RGB, cap size. No binarisation or sharpening
    because aggressive filters hurt OCR-free models such as Donut."""
    img = ImageOps.exif_transpose(img).convert("RGB")
    w, h = img.size
    scale = max_side / max(w, h)
    if scale < 1:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return img


def prepare(path) -> List[Image.Image]:
    """PDF or image file -> list of enhanced page images (first MAX_PAGES pages)."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        pages = pdf_to_images(path)
    elif suffix in IMAGE_SUFFIXES:
        pages = [Image.open(path)]
    else:
        raise ValueError(f"Unsupported file type: {suffix}")
    return [enhance(p) for p in pages]
