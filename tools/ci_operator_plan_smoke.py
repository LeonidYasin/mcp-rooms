"""Actions integration: real exact-source wheelhouse, synthetic host observations.

Does not inspect/modify runner host accounts/units/ports, run app or create a key.
"""
import json
from pathlib import Path
import runpy
import sys

ROOT=Path(__file__).resolve().parents[1]
m=runpy.run_path(str(ROOT/'tools/operator_plan.py'))
observations={'format':'mcp-rooms/host-observation/v1',
    'target':{'python':'3.12','system':'Linux','machine':'x86_64'},
    'user_absent':True,'group_absent':True,
    'paths_absent':{p:True for p in m['TARGETS']},'port_free':True,
    'systemd_available':True,'python312_venv_available':True,'landlock_abi':3,
    'free_bytes':2*1024**3,'available_memory_bytes':0}
from hashlib import sha256
lock_hash=sha256((ROOT/'operator/runtime-linux-x86_64-py312.lock').read_bytes()).hexdigest()
result=m['build_plan'](Path(sys.argv[1]),sys.argv[2],lock_hash,
    'https://candidate.invalid/rooms-test/mcp',observations)
assert result['bundle_verified']['distributions']>1
assert not result['host_probe_performed'] and not result['install_authorized']
assert not result['runtime_resources_accepted'] and len(result['steps'])==7
print('OPERATOR PLAN SMOKE PASS: '+json.dumps({'source_sha':result['source_sha'],
    'plan_sha256':result['plan_sha256'],'host_probe':False,'installed':False,
    'observations':'synthetic-unattested','steps':7},sort_keys=True))
