"""Pure helpers/guard for Actions-only privileged fixture; not installer tests."""
from pathlib import Path
import runpy
import struct
import zlib
import pytest
ROOT=Path(__file__).resolve().parents[1]
m=runpy.run_path(str(ROOT/'tools/ci_candidate_unit.py'))


def test_ci_privileged_harness_refuses_without_actions(monkeypatch):
    monkeypatch.delenv('GITHUB_ACTIONS',raising=False)
    with pytest.raises(RuntimeError,match='disposable_actions_root_only'):
        m['main'](Path('/missing'),'a'*40)


def test_png_synthetic_metadata_and_crc():
    value=m['synthetic_png'](4,3);assert value.startswith(b'\x89PNG\r\n\x1a\n')
    offset=8;chunks={}
    while offset<len(value):
        size=struct.unpack('>I',value[offset:offset+4])[0]
        kind=value[offset+4:offset+8];data=value[offset+8:offset+8+size]
        checksum=struct.unpack('>I',value[offset+8+size:offset+12+size])[0]
        assert zlib.crc32(kind+data)&0xffffffff==checksum
        chunks[kind]=data;offset+=12+size
    assert struct.unpack('>II',chunks[b'IHDR'][:8])==(4,3)
    assert len(zlib.decompress(chunks[b'IDAT']))==3*(1+4*3)
    assert b'CI-SYNTHETIC-METADATA' in chunks[b'tEXt']


def test_jpeg_dimension_parser():
    # Synthetic SOF segment only; no actual decoder involved.
    sof=b'\x08'+struct.pack('>HH',1200,1600)+b'\x03'+b'\0'*9
    value=b'\xff\xd8\xff\xc0'+struct.pack('>H',len(sof)+2)+sof+b'\xff\xd9'
    assert m['jpeg_dimensions'](value)==(1600,1200)


@pytest.mark.parametrize('value',[b'',b'png',b'\xff\xd8\xff\xd9',b'\xff\xd8\xff\xc0\x00\x01\xff\xd9',b'\xff\xd8\xff\xc0\x00\x20\xff\xd9'])
def test_invalid_jpeg_refused(value):
    with pytest.raises(ValueError):m['jpeg_dimensions'](value)
