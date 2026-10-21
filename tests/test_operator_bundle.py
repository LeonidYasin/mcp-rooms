"""Integrity fixtures only; package download/build/install happens in Actions job."""
from hashlib import sha256
import json
import os
from pathlib import Path
import runpy
import shutil
import zipfile
import pytest

ROOT=Path(__file__).resolve().parents[1]
m=runpy.run_path(str(ROOT/'tools/operator_bundle.py'))
Error=m['BundleError']


def wheel(directory,name,version='1.0',extra=b'payload'):
    path=directory/(name.replace('-','_')+'-'+version+'-py3-none-any.whl')
    with zipfile.ZipFile(path,'w') as z:
        z.writestr(name.replace('-','_')+'-'+version+'.dist-info/METADATA',f'Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n\n')
        z.writestr('synthetic.txt',extra)
    return path


@pytest.fixture
def bundle(tmp_path,monkeypatch):
    tmp_path.chmod(0o700);root=tmp_path/'bundle';root.mkdir(mode=0o700)
    (root/'wheels').mkdir(mode=0o700)
    wheel(root/'wheels','mcp-rooms','0.1.0a1');wheel(root/'wheels','dependency')
    # Unit fixture is platform-independent; actual verifier runs natively in job.
    monkeypatch.setitem(m['seal'].__globals__,'_target',lambda:dict(m['TARGET']))
    lock=m['render_lock'](m['_wheels'](root/'wheels'),runtime_only=True)
    manifest=m['seal'](root,'1'*40,lock)
    return root,sha256(lock.encode()).hexdigest(),manifest


def verify(x,**kw):
    root,digest,_=x
    return m['verify'](root,kw.pop('source','1'*40),kw.pop('lock',digest),**kw)


def test_locked_manifest_has_full_dependencies_and_no_runtime_state(bundle):
    result=verify(bundle);root,_,manifest=bundle
    assert result['ok'] and result['distributions']==2
    assert result['kind']=='locked-wheelhouse-not-vps-installer'
    assert set(p.name for p in root.iterdir())=={'wheels','manifest.json','runtime.lock','install.lock','OPERATOR.md'}
    assert 'mcp-rooms==' not in (root/'runtime.lock').read_text()
    assert 'mcp-rooms==0.1.0a1 --hash=sha256:' in (root/'install.lock').read_text()
    assert all(len(p['sha256'])==64 for p in manifest['files'])


@pytest.mark.parametrize('change',['wheel','manifest','extra','symlink','hardlink','lock','install','source','external_lock','directory_mode','file_mode','unknown_wheel','missing_project','target','duplicate_key','seed'])
def test_integrity_failures_refused(bundle,change):
    root,digest,manifest=bundle;p=next((root/'wheels').iterdir())
    if change=='wheel':p.write_bytes(b'corrupt')
    elif change=='manifest':(root/'manifest.json').write_text('{}')
    elif change=='extra':(root/'owner.key').write_text('synthetic forbidden')
    elif change=='symlink':p.unlink();p.symlink_to(root/'runtime.lock')
    elif change=='hardlink':os.link(p,root/'alias')
    elif change=='lock':(root/'runtime.lock').write_text('dependency>=0\n')
    elif change=='install':(root/'install.lock').write_text('dependency\n')
    elif change=='source':
        with pytest.raises(Error):verify(bundle,source='2'*40)
        return
    elif change=='external_lock':
        with pytest.raises(Error):verify(bundle,lock='3'*64)
        return
    elif change=='directory_mode':root.chmod(0o755)
    elif change=='file_mode':p.chmod(0o666)
    elif change=='unknown_wheel':(root/'wheels'/'unexpected.txt').write_text('not a wheel')
    elif change=='missing_project':next((root/'wheels').glob('mcp_rooms*')).unlink()
    elif change=='target':manifest['target']['machine']='aarch64'
    elif change=='duplicate_key':(root/'manifest.json').write_text('{"format":1,"format":1}')
    elif change=='seed':manifest['kind']='discovery-not-installable'
    if change in ('target','seed'):(root/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises((Error,OSError,zipfile.BadZipFile)):verify(bundle)


def test_discovery_requires_explicit_unaccepted_mode(bundle):
    root,digest,manifest=bundle;manifest['kind']='discovery-not-installable'
    (root/'manifest.json').write_text(json.dumps(manifest))
    assert verify(bundle,allow_seed=True)['kind']=='discovery-not-installable'
    with pytest.raises(Error):verify(bundle)


def test_new_target_never_overwrites_or_nests_symlink(tmp_path):
    tmp_path.chmod(0o700);root=m['_new'](tmp_path/'new')
    with pytest.raises(FileExistsError):m['_new'](root)
    alias=tmp_path/'alias';alias.symlink_to(root,target_is_directory=True)
    with pytest.raises(Error):m['_new'](alias)


def test_archive_allowlist_does_not_include_credentials_or_state(bundle,tmp_path):
    root,_,_=bundle;out=tmp_path/'bundle.tar.gz'
    report=m['archive'](root,out)
    import tarfile
    with tarfile.open(out) as t:
        names=t.getnames()
        assert set(names)=={'wheels','manifest.json','runtime.lock','install.lock','OPERATOR.md'}|{'wheels/'+p.name for p in (root/'wheels').iterdir()}
        assert all(i.uid==0 and i.mtime==0 and i.mode==(0o700 if i.isdir() else 0o600) for i in t.getmembers())
    assert report['sha256']==sha256(out.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):m['archive'](root,out)


@pytest.mark.parametrize('name',['../../bad','bad\nname','bad@host','',True])
def test_unsafe_distribution_names_rejected(name):
    with pytest.raises(Error):m['_name'](name)


def test_target_mismatch_refused_before_filesystem(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setitem(m['_target'].__globals__,'sys',SimpleNamespace(version_info=(3,11)))
    with pytest.raises(Error,match='operator_target_unsupported'):m['_target']()
