"""Synthetic images only. Optional media dependency is installed by media CI legs."""
from hashlib import sha256
from io import BytesIO
import pytest
PIL = pytest.importorskip('PIL', reason='optional media requires Python >=3.11')
from PIL import Image, PngImagePlugin
from mcp_rooms.domain import DomainError
from mcp_rooms import media_image as m


def image_bytes(fmt='PNG', size=(20, 10), mode='RGB', color='red', **kw):
    with Image.new(mode, size, color) as image, BytesIO() as out:
        image.save(out, format=fmt, **kw)
        return out.getvalue()


def reject(code, payload, mime='image/png'):
    with pytest.raises(DomainError) as e:
        m.normalize_photo(payload, mime)
    assert e.value.code == code


@pytest.mark.parametrize('fmt,mime', [('PNG', 'image/png'), ('JPEG', 'image/jpeg')])
def test_fresh_jpeg_and_digest(fmt, mime):
    result = m.normalize_photo(image_bytes(fmt), mime)
    assert result.content_type == 'image/jpeg' and result.source_format == fmt
    assert result.sha256 == sha256(result.data).hexdigest()
    assert (result.width, result.height) == (20, 10)
    with Image.open(BytesIO(result.data)) as out:
        out.load()
        assert out.format == 'JPEG' and out.mode == 'RGB'
        assert not out.getexif()
        assert not set(out.info) & {'exif', 'icc_profile', 'comment', 'xmp'}


def test_png_text_and_transparency_removed():
    info = PngImagePlugin.PngInfo()
    info.add_text('private', 'GPS SECRET metadata')
    result = m.normalize_photo(image_bytes(mode='RGBA', color=(0, 0, 0, 0), pnginfo=info), 'image/png')
    assert b'GPS SECRET' not in result.data
    with Image.open(BytesIO(result.data)) as out:
        assert min(out.getpixel((5, 5))) >= 250
        assert 'private' not in out.info


def test_exif_orientation_applied_metadata_discarded():
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = 'PRIVATE DESCRIPTION'
    result = m.normalize_photo(image_bytes('JPEG', exif=exif), 'image/jpeg')
    assert (result.width, result.height) == (10, 20)
    assert b'PRIVATE DESCRIPTION' not in result.data
    with Image.open(BytesIO(result.data)) as out:
        assert not out.getexif()


def test_no_upscale_and_bounded_resize():
    small = m.normalize_photo(image_bytes(size=(1, 2)), 'image/png')
    assert (small.width, small.height) == (1, 2)
    large = m.normalize_photo(image_bytes(size=(2000, 1000)), 'image/png')
    assert (large.width, large.height) == (1600, 800)


@pytest.mark.parametrize('payload', [b'', bytearray(b'x'), 'x', None])
def test_invalid_bytes(payload):
    reject('media_invalid_bytes', payload)


@pytest.mark.parametrize('mime', ['image/gif', 'image/webp', 'image/svg+xml', '', None, [], 'image/png; charset=utf-8'])
def test_disallowed_type(mime):
    reject('media_type_not_allowed', image_bytes(), mime)


def test_spoofed_and_corrupt_and_truncated():
    reject('media_type_mismatch', image_bytes('JPEG'))
    reject('media_type_mismatch', b'not an image')
    reject('media_invalid_image', b'\x89PNG\r\n\x1a\n' + b'broken')
    reject('media_invalid_image', image_bytes()[:-15])
    reject('media_invalid_image', image_bytes('JPEG')[:100], 'image/jpeg')


def test_animation_rejected():
    with Image.new('RGB', (4, 4), 'red') as a, Image.new('RGB', (4, 4), 'blue') as b, BytesIO() as out:
        a.save(out, format='PNG', save_all=True, append_images=[b], duration=100, loop=0)
        reject('media_animation_not_allowed', out.getvalue())


def test_caps_before_decode_and_on_output(monkeypatch):
    payload = image_bytes()
    monkeypatch.setattr(m, 'MAX_INPUT_BYTES', len(payload) - 1)
    reject('media_input_too_large', payload)
    monkeypatch.setattr(m, 'MAX_INPUT_BYTES', len(payload))
    monkeypatch.setattr(m, 'MAX_SIDE', 19)
    reject('media_dimensions_exceeded', payload)
    monkeypatch.setattr(m, 'MAX_SIDE', 6000)
    monkeypatch.setattr(m, 'MAX_PIXELS', 199)
    reject('media_dimensions_exceeded', payload)
    monkeypatch.setattr(m, 'MAX_PIXELS', 200)
    monkeypatch.setattr(m, 'MAX_OUTPUT_BYTES', 50)
    reject('media_output_too_large', payload)


def test_pillow_bomb_guard_remains_enabled(monkeypatch):
    payload = image_bytes()
    assert Image.MAX_IMAGE_PIXELS is not None
    monkeypatch.setattr(Image, 'MAX_IMAGE_PIXELS', 150)
    reject('media_dimensions_exceeded', payload)
