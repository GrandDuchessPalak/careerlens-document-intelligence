from PIL import Image

from src.pdf_to_image import (
    MAX_IMAGE_SIDE,
    UnsupportedFileTypeError,
    _normalize_image,
    load_document_images,
)


def test_load_image(tmp_path):
    path = tmp_path / "test.png"

    Image.new("RGB", (500, 500)).save(path)

    images = load_document_images(path)

    assert len(images) == 1
    assert images[0].mode == "RGB"


def test_large_image_downscaled():
    image = Image.new("RGB", (3000, 1000))

    result = _normalize_image(image)

    assert max(result.size) == MAX_IMAGE_SIDE


def test_unsupported_file():
    from pytest import raises

    with raises(UnsupportedFileTypeError):
        load_document_images("test.txt")