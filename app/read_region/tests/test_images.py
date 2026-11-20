import io
from dataclasses import replace

import pytest
from PIL import Image

from vision_core.images import ImageFailure, Limits, box_from_parameters, view


def original():
    image = Image.new("RGB", (2048, 1536))
    image.putdata(
        [
            ((x % 251), (y % 253), ((x + y) % 247))
            for y in range(1536)
            for x in range(2048)
        ]
    )
    data = io.BytesIO()
    image.save(data, format="PNG")
    return image, data.getvalue()


def test_full_image_source_pixels_are_unchanged():
    source, data = original()
    output, meta = view(data, box_from_parameters({}))
    with Image.open(io.BytesIO(output)) as result:
        assert (
            result.size == (2048, 1536)
            and result.tobytes() == source.tobytes()
        )
    assert meta["resized"] is False and meta["crop_pixels"] == [
        0,
        0,
        2048,
        1536,
    ]


def test_native_400_by_300_region_is_exact_original_roi():
    source, data = original()
    output, meta = view(data, [0.125, 0.125, 0.3203125, 0.3203125])
    with Image.open(io.BytesIO(output)) as result:
        assert result.size == (400, 300)
        assert result.tobytes() == source.crop((256, 192, 656, 492)).tobytes()
    assert meta["crop_pixels"] == [256, 192, 656, 492]


@pytest.mark.parametrize(
    "value", [True, "0.5", None, float("nan"), float("inf"), -0.1, 1.1]
)
def test_invalid_coordinate_is_rejected(value):
    with pytest.raises(ImageFailure):
        box_from_parameters(
            {"x_min": value, "y_min": 0, "x_max": 1, "y_max": 1}
        )


def test_output_cap_and_malformed_input():
    with pytest.raises(ImageFailure, match="INVALID_IMAGE"):
        view(b"invalid", [0, 0, 1, 1])
    source, data = original()
    with pytest.raises(ImageFailure, match="OUTPUT_LIMIT_EXCEEDED"):
        view(data, [0, 0, 1, 1], replace(Limits(), output_bytes=32))


def grayscale16_png():
    import struct

    source = Image.frombytes(
        "I;16",
        (4, 2),
        struct.pack("<8H", 1000, 2000, 4096, 65535, 256, 1024, 32768, 60000),
    )
    data = io.BytesIO()
    source.save(data, format="PNG")
    return source, data.getvalue()


def test_16bit_grayscale_full_keeps_distinct_native_samples():
    source, data = grayscale16_png()
    output, meta = view(data, [0, 0, 1, 1])
    with Image.open(io.BytesIO(output)) as result:
        assert list(result.get_flattened_data()) == list(
            source.get_flattened_data()
        )
        assert (
            result.getpixel((0, 0)) == 1000 and result.getpixel((1, 0)) == 2000
        )
    assert output[24] == 16 and output[25] == 0
    assert meta["resized"] is False


def test_16bit_grayscale_crop_keeps_exact_native_roi():
    source, data = grayscale16_png()
    output, meta = view(data, [0.25, 0, 0.75, 1])
    with Image.open(io.BytesIO(output)) as result:
        assert result.size == (2, 2)
        assert list(result.get_flattened_data()) == list(
            source.crop((1, 0, 3, 2)).get_flattened_data()
        )
    assert output[24] == 16 and meta["crop_pixels"] == [1, 0, 3, 2]


@pytest.mark.parametrize("color_type,channels", [(2, 3), (4, 2), (6, 4)])
def test_unsupported_16bit_color_rejected_before_loss(color_type, channels):
    import struct
    import zlib

    def chunk(kind, body):
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
        )

    data = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(
            b"IHDR", struct.pack(">IIBBBBB", 1, 1, 16, color_type, 0, 0, 0)
        )
        + chunk(
            b"IDAT",
            zlib.compress(
                b"\x00"
                + struct.pack(">" + "H" * channels, *([1000] * channels))
            ),
        )
        + chunk(b"IEND", b"")
    )
    with pytest.raises(ImageFailure, match="UNSUPPORTED_BIT_DEPTH"):
        view(data, [0, 0, 1, 1])


def test_16bit_grayscale_transparency_survives_full_and_crop():
    source, _ = grayscale16_png()
    data = io.BytesIO()
    source.save(data, format="PNG", transparency=1000)
    for box, pixels in [
        ([0, 0, 1, 1], (0, 0, 4, 2)),
        ([0, 0, 0.75, 1], (0, 0, 3, 2)),
    ]:
        output, meta = view(data.getvalue(), box)
        with Image.open(io.BytesIO(output)) as result:
            assert list(result.get_flattened_data()) == list(
                source.crop(pixels).get_flattened_data()
            )
            assert result.info.get("transparency") == 1000
        assert output[24] == 16 and meta["resized"] is False
