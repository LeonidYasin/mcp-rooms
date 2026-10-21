"""CI-only wheelhouse preparation and offline integrity verifier, no VPS actions.

Seed is explicitly unaccepted dependency discovery. Only committed hash-lock builds
are install candidates. Neither mode bootstraps state, calls systemctl or binds ports.
"""
import argparse
import base64
from email.parser import BytesParser
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import gzip
import zipfile

FORMAT='mcp-rooms/operator-wheelhouse/v1'
TARGET={'python':'3.12','system':'Linux','machine':'x86_64'}
MAX_FILES=80
MAX_FILE=48*1024*1024
MAX_TOTAL=192*1024*1024
MAX_META=128*1024
MAX_WHEEL_META=256*1024
ROOT=Path(__file__).resolve().parents[1]


class BundleError(Exception): pass


def _target():
    if sys.version_info[:2]!=(3,12) or platform.system()!='Linux' or platform.machine()!='x86_64':
        raise BundleError('operator_target_unsupported')
    return dict(TARGET)


def _name(value):
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}',value):
        raise BundleError('operator_invalid_distribution')
    return re.sub(r'[-_.]+','-',value).lower()


def _sha(value):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{40}',value):
        raise BundleError('operator_source_sha_required')
    return value


def _file(path, maximum=MAX_FILE):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        before=os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink!=1
                or before.st_uid!=os.geteuid() or before.st_mode&0o022 or not 0<before.st_size<=maximum):
            raise BundleError('operator_unsafe_file')
        digest=sha256();size=0
        while size<=maximum:
            block=os.read(fd,min(65536,maximum+1-size))
            if not block:break
            size+=len(block);digest.update(block)
        after,named=os.fstat(fd),path.lstat()
        fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_nlink')
        if size!=before.st_size or any(getattr(before,k)!=getattr(after,k) or getattr(after,k)!=getattr(named,k) for k in fields):
            raise BundleError('operator_changed_file')
        return {'sha256':digest.hexdigest(),'byte_size':size}
    finally:os.close(fd)


def _wheel(path):
    if not re.fullmatch(r'[A-Za-z0-9_.+!-]{1,220}\.whl',path.name):
        raise BundleError('operator_invalid_wheel_name')
    info=_file(path)
    with zipfile.ZipFile(path) as z:
        names=[i for i in z.infolist() if i.filename.endswith('.dist-info/METADATA')]
        if len(names)!=1 or names[0].file_size>MAX_WHEEL_META:
            raise BundleError(f'operator_invalid_wheel_metadata:{path.name}:entries={len(names)}:bytes={names[0].file_size if len(names)==1 else -1}')
        # No extracting wheels here. pip performs its own wheel compatibility check.
        msg=BytesParser().parsebytes(z.read(names[0]))
        if len(msg.get_all('Name',[]))!=1 or len(msg.get_all('Version',[]))!=1:
            raise BundleError('operator_invalid_wheel_metadata')
        name=_name(msg['Name']);version=msg['Version']
        if not re.fullmatch(r'[A-Za-z0-9.!+_-]{1,80}',version):
            raise BundleError('operator_invalid_wheel_metadata')
        return {'name':name,'version':version,'wheel':path.name,**info}


def _wheels(directory):
    paths=sorted(directory.iterdir())
    if not 1<=len(paths)<=MAX_FILES:raise BundleError('operator_wheel_count')
    result=[_wheel(p) for p in paths]
    if len({p['name'] for p in result})!=len(result) or sum(p['byte_size'] for p in result)>MAX_TOTAL:
        raise BundleError('operator_wheel_count')
    return sorted(result,key=lambda p:p['name'])


def render_lock(distributions, *, runtime_only=False):
    rows=['# Linux x86_64 CPython3.12 wheel hashes; generated in Actions, review before adoption.']
    for d in sorted(distributions,key=lambda p:p['name']):
        if runtime_only and d['name']=='mcp-rooms':continue
        rows.append(f"{d['name']}=={d['version']} --hash=sha256:{d['sha256']}")
    return '\n'.join(rows)+'\n'


def _pairs(items):
    result={}
    for k,v in items:
        if k in result:raise BundleError('operator_duplicate_manifest_key')
        result[k]=v
    return result


def _directory(path):
    st=path.lstat()
    if (not path.is_absolute() or path.resolve()!=path or not stat.S_ISDIR(st.st_mode)
            or st.st_uid!=os.geteuid() or stat.S_IMODE(st.st_mode)!=0o700):
        raise BundleError('operator_private_directory_required')


def _new(path):
    path=Path(path)
    if not path.is_absolute() or path.resolve()!=path:raise BundleError('operator_private_directory_required')
    _directory(path.parent);path.mkdir(mode=0o700);_directory(path)
    return path


def _expected(root):
    # Explicit public allowlist only: no recursive packaging of checkout/state.
    files=['runtime.lock','install.lock','OPERATOR.md']
    files+=['wheels/'+p.name for p in sorted((root/'wheels').iterdir())]
    return files


def seal(root, source_sha, runtime_lock, *, seed=False):
    _target();source_sha=_sha(source_sha)
    _directory(root);_directory(root/'wheels')
    distributions=_wheels(root/'wheels')
    own=[p for p in distributions if p['name']=='mcp-rooms']
    if len(own)!=1:raise BundleError('operator_project_wheel_required')
    generated=render_lock(distributions,runtime_only=True)
    if generated!=runtime_lock:raise BundleError('operator_runtime_lock_mismatch')
    (root/'runtime.lock').write_text(runtime_lock,encoding='utf-8')
    (root/'install.lock').write_text(render_lock(distributions),encoding='utf-8')
    (root/'OPERATOR.md').write_text((ROOT/'operator/OPERATOR.md').read_text(),encoding='utf-8')
    paths=_expected(root)
    manifest={'format':FORMAT,'source_sha':source_sha,'target':dict(TARGET),
              'kind':'discovery-not-installable' if seed else 'locked-wheelhouse-not-vps-installer',
              'runtime_lock_sha256':sha256(runtime_lock.encode()).hexdigest(),
              'distributions':distributions,
              'files':[{'path':p,**_file(root/p)} for p in paths]}
    (root/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    return manifest


def verify(root, expected_source, expected_lock_sha, *, allow_seed=False):
    _target();_sha(expected_source);root=Path(root);_directory(root);_directory(root/'wheels')
    if type(expected_lock_sha) is not str or not re.fullmatch('[0-9a-f]{64}',expected_lock_sha):
        raise BundleError('operator_external_lock_hash_required')
    if set(p.name for p in root.iterdir())!={'wheels','runtime.lock','install.lock','OPERATOR.md','manifest.json'}:
        raise BundleError('operator_unexpected_file')
    _file(root/'manifest.json',MAX_META)
    try:m=json.loads((root/'manifest.json').read_text(),object_pairs_hook=_pairs)
    except (ValueError,UnicodeError,RecursionError):raise BundleError('operator_invalid_manifest') from None
    if (type(m) is not dict or set(m)!={'format','source_sha','target','kind','runtime_lock_sha256','distributions','files'}
            or m['format']!=FORMAT or m['source_sha']!=expected_source or m['target']!=TARGET
            or m['runtime_lock_sha256']!=expected_lock_sha
            or m['kind'] not in (('locked-wheelhouse-not-vps-installer','discovery-not-installable') if allow_seed else ('locked-wheelhouse-not-vps-installer',))):
        raise BundleError('operator_manifest_mismatch')
    runtime=(root/'runtime.lock').read_bytes();install=(root/'install.lock').read_bytes()
    if sha256(runtime).hexdigest()!=expected_lock_sha:raise BundleError('operator_runtime_lock_mismatch')
    actual=_wheels(root/'wheels')
    if (actual!=m['distributions'] or len([p for p in actual if p['name']=='mcp-rooms'])!=1
            or render_lock(actual,runtime_only=True).encode()!=runtime or render_lock(actual).encode()!=install):
        raise BundleError('operator_runtime_lock_mismatch')
    expected=[{'path':p,**_file(root/p)} for p in _expected(root)]
    if expected!=m['files']:raise BundleError('operator_file_hash_mismatch')
    return {'ok':True,'source_sha':expected_source,'kind':m['kind'],
            'distributions':len(actual),'wheel_bytes':sum(p['byte_size'] for p in actual),
            'runtime_lock_sha256':expected_lock_sha}


def archive(root, destination):
    # Archive is not executed/extracted by this function. Verify external digest first.
    files=['manifest.json']+_expected(root)
    with open(destination,'xb') as out, gzip.GzipFile(filename='',mode='wb',fileobj=out,mtime=0) as gz, tarfile.open(fileobj=gz,mode='w') as tar:
        ti=tarfile.TarInfo('wheels');ti.type=tarfile.DIRTYPE;ti.mode=0o700;ti.mtime=0
        tar.addfile(ti)
        for rel in sorted(files):
            _file(root/rel)
            ti=tar.gettarinfo(str(root/rel),arcname=rel)
            ti.uid=ti.gid=0;ti.uname=ti.gname='';ti.mtime=0;ti.mode=0o600
            with (root/rel).open('rb') as f:tar.addfile(ti,f)
    return _file(Path(destination),MAX_TOTAL)


def prepare(project_wheel, output, source_sha, lock_path=None):
    _target();_sha(source_sha)
    root=_new(Path(output));(root/'wheels').mkdir(mode=0o700)
    _wheel(Path(project_wheel))
    command=[sys.executable,'-m','pip','--isolated','download','--disable-pip-version-check',
             '--only-binary=:all:','--dest',str(root/'wheels')]
    if lock_path is None:
        # Discovery only. Adoption requires a separate reviewed repository commit.
        command+=[str(Path(project_wheel).resolve())+'[media]']
    else:
        lock_path=Path(lock_path);_file(lock_path,MAX_META)
        command+=['--require-hashes','-r',str(lock_path)]
        shutil.copyfile(project_wheel,root/'wheels'/Path(project_wheel).name)
    subprocess.run(command,check=True,timeout=180)
    wheels=_wheels(root/'wheels')
    runtime=render_lock(wheels,runtime_only=True) if lock_path is None else lock_path.read_text(encoding='utf-8')
    manifest=seal(root,source_sha,runtime,seed=lock_path is None)
    report=verify(root,source_sha,manifest['runtime_lock_sha256'],allow_seed=lock_path is None)
    if lock_path is None:
        print('LOCK_BASE64='+base64.b64encode(runtime.encode()).decode())
    print('BUNDLE_VERIFY='+json.dumps(report,sort_keys=True))
    packed=archive(root,Path(str(root)+'.tar.gz'))
    print('BUNDLE_ARCHIVE='+json.dumps(packed,sort_keys=True))
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--wheel',required=True);p.add_argument('--output',required=True)
    p.add_argument('--source-sha',required=True);p.add_argument('--lock')
    a=p.parse_args();os.umask(0o077)
    prepare(a.wheel,a.output,a.source_sha,a.lock)


if __name__=='__main__':main()
