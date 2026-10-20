"""Optional, in-memory photo normalization. NOT an upload endpoint or sandbox.

Untrusted decode must run in an OS-limited worker before public integration.
No original bytes, filename, storage path, URL, identity or publication is accepted.
"""
from hashlib import sha256
from io import BytesIO
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError
from .domain import DomainError

from .media_contract import (MAX_INPUT_BYTES, MAX_PIXELS, MAX_SIDE, OUTPUT_SIDE,
                             MAX_OUTPUT_BYTES, NormalizedPhoto)
_MIMES = {'image/jpeg': 'JPEG', 'image/png': 'PNG'}

class _Output(BytesIO):
    def write(self, data):
        if self.tell() + len(data) > MAX_OUTPUT_BYTES:
            raise DomainError('media_output_too_large')
        return super().write(data)


def _check(image, expected):
    if image.format != expected:
        raise DomainError('media_type_mismatch')
    w, h = image.size
    if min(w, h) < 1 or max(w, h) > MAX_SIDE or w * h > MAX_PIXELS:
        raise DomainError('media_dimensions_exceeded')
    if getattr(image, 'n_frames', 1) != 1:
        raise DomainError('media_animation_not_allowed')


def normalize_photo(payload: bytes, declared_type: str) -> NormalizedPhoto:
    """Return a fresh JPEG without forwarding original metadata.

    Limits are fixed, not caller-controlled. Not a malware scanner, authenticity
    verifier, steganography scrubber or hard CPU/RAM bound. Transport must enforce
    its own streaming body cap BEFORE building payload. No filesystem writes.
    """
    if type(payload) is not bytes or not payload:
        raise DomainError('media_invalid_bytes')
    if len(payload) > MAX_INPUT_BYTES:
        raise DomainError('media_input_too_large')
    if not isinstance(declared_type, str) or declared_type not in _MIMES:
        raise DomainError('media_type_not_allowed')
    expected = _MIMES[declared_type]
    magic = payload.startswith(b'\xff\xd8\xff') if expected == 'JPEG' else payload.startswith(b'\x89PNG\r\n\x1a\n')
    if not magic:
        raise DomainError('media_type_mismatch')
    try:
        # Do not disable Pillow's decompression-bomb or PNG text protections.
        # Warning-filter isolation is another reason for a dedicated worker.
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(payload), formats=['JPEG', 'PNG']) as probe:
                _check(probe, expected)
                probe.verify()
            with Image.open(BytesIO(payload), formats=['JPEG', 'PNG']) as decoded:
                _check(decoded, expected)
                decoded.load()
                with ImageOps.exif_transpose(decoded) as oriented:
                    oriented.thumbnail((OUTPUT_SIDE, OUTPUT_SIDE), Image.Resampling.LANCZOS)
                    # A new RGB canvas is the metadata boundary. Never forward info,
                    # EXIF, XMP, ICC, comments, PNG text or encoder metadata.
                    with Image.new('RGB', oriented.size, 'white') as clean:
                        with oriented.convert('RGBA') as rgba:
                            with rgba.getchannel('A') as alpha:
                                clean.paste(rgba, mask=alpha)
                        with _Output() as output:
                            clean.save(output, format='JPEG', quality=85,
                                       optimize=False, progressive=False,
                                       exif=b'', icc_profile=None)
                            data = output.getvalue()
                        return NormalizedPhoto(data, sha256(data).hexdigest(),
                                               clean.width, clean.height, expected)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise DomainError('media_dimensions_exceeded') from None
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, EOFError):
        # Stable public-safe error, without raw codec messages or metadata.
        raise DomainError('media_invalid_image') from None
