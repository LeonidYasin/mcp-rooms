"""Read-only operator proposal from trusted exact-source verifier; never an installer.

No application imports, processes, sockets, root/account/unit/service operations,
bootstrap, mutation or credential reads. Supplied observations are NOT attestation.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import runpy
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
FORMAT='mcp-rooms/operator-plan/v1'
USER='mcp-rooms-candidate'
UNIT=USER+'.service'
BASE='/opt/'+USER
STATE='/var/lib/'+USER
PORT=8766
TARGETS=(BASE,STATE,'/etc/systemd/system/'+UNIT,
         '/etc/systemd/system/'+UNIT+'.d')


class PlanError(Exception):pass


def _sha(value,length,code):
    if type(value) is not str or re.fullmatch('[0-9a-f]{'+str(length)+'}',value) is None:
        raise PlanError(code)
    return value


def _resource(value):
    if type(value) is not str or not 1<=len(value)<=256 or not value.isascii():
        raise PlanError('operator_invalid_resource')
    try:
        u=urlsplit(value);host=u.hostname
        port=u.port
    except ValueError:raise PlanError('operator_invalid_resource') from None
    if (u.scheme!='https' or not host or u.username is not None or u.password is not None
            or port is not None or u.query or u.fragment or u.netloc!=host
            or not re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)*',host)
            or not re.fullmatch(r'/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*/mcp',u.path)
            or value!='https://'+host+u.path):
        raise PlanError('operator_invalid_resource')
    return value


def validate_observations(value):
    # A future installer MUST re-read these immediately before effects. JSON is
    # only a reviewed-input consistency check; it cannot prove remote host state.
    keys={'format','target','user_absent','group_absent','paths_absent','port_free',
          'systemd_available','python312_venv_available','landlock_abi','free_bytes',
          'available_memory_bytes'}
    if type(value) is not dict or set(value)!=keys or value['format']!='mcp-rooms/host-observation/v1':
        raise PlanError('operator_invalid_observations')
    if value['target']!={'python':'3.12','system':'Linux','machine':'x86_64'}:
        raise PlanError('operator_target_unsupported')
    for field in ('user_absent','group_absent','port_free','systemd_available','python312_venv_available'):
        if type(value[field]) is not bool or not value[field]:
            raise PlanError('operator_host_prerequisite_refused')
    paths=value['paths_absent']
    if type(paths) is not dict or set(paths)!=set(TARGETS) or any(type(v) is not bool or not v for v in paths.values()):
        raise PlanError('operator_existing_target_refused')
    for field in ('landlock_abi','free_bytes','available_memory_bytes'):
        if type(value[field]) is not int or not 0<=value[field]<2**63:
            raise PlanError('operator_invalid_observations')
    if value['landlock_abi']<3:raise PlanError('operator_landlock_unavailable')
    # Necessary lower floor only; NOT a promise that host capacity is adequate.
    if value['free_bytes']<2*1024**3:raise PlanError('operator_disk_floor_refused')
    return value


def build_plan(bundle,expected_source,expected_lock_sha,resource,observations):
    expected_source=_sha(expected_source,40,'operator_source_sha_required')
    expected_lock_sha=_sha(expected_lock_sha,64,'operator_lock_hash_required')
    resource=_resource(resource);validate_observations(observations)
    # Trusted repository tool, NOT code taken from the wheelhouse/archive.
    verifier=runpy.run_path(str(ROOT/'tools/operator_bundle.py'))['verify']
    verified=verifier(Path(bundle),expected_source,expected_lock_sha)
    observation_digest=sha256(json.dumps(observations,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    release=BASE+'/releases/'+expected_source
    plan={
        'format':FORMAT,'kind':'review-proposal-not-executable-installer',
        'source_sha':expected_source,'runtime_lock_sha256':expected_lock_sha,
        'bundle_verified':verified,'observation_digest':observation_digest,
        'observation_authority':'caller-supplied-unattested; recheck before every effect',
        'host_probe_performed':False,'install_authorized':False,
        'runtime_resources_accepted':False,
        'identity':{'user':USER,'group':USER,'unit':UNIT,'boot_enabled':False},
        'layout':{'base':BASE,'release':release,'venv':release+'/venv',
                  'state_parent':STATE,'fresh_profile':STATE+'/owner-first',
                  'state_parent_mode':'0700','profile_mode':'0700',
                  'release_policy':'root-owned; service read-only; no code writes'},
        'network':{'listen_host':'127.0.0.1','listen_port':PORT,'resource':resource,
                   'create_https_route':False,'trust_proxy_headers':False},
        'install_policy':{'fresh_only':True,'discovery_allowed':False,
                          'network_fallback':False,'hashes_required':True,
                          'originals_or_live_db_import':False},
        'steps':[
            {'id':'preflight','effect':'none','requirements':['fresh separately approved host observation','independent archive SHA256 check before extraction','recheck absent user/group/paths/port immediately before effect','approved measured capacity/disk/retention budget']},
            {'id':'offline_install','effect':'future-explicit-approval','requirements':['new isolated identity/release/venv','pip --no-index --only-binary=:all: --require-hashes','pip check','no install scripts as root; never inherit PAT or env']},
            {'id':'bootstrap','effect':'future-explicit-real-key-approval','requirements':['fresh private profile only','one owner credential delivered privately once; never stdout/log','no recovery promotion or live DB reuse']},
            {'id':'loopback_start','effect':'future-explicit-approval','requirements':['fixed unit identity/paths/port','one worker and one upload admission','native sandbox preflight before serving','no Caddy/other-service changes; no autostart']},
            {'id':'health','effect':'future-approved-read-only','requirements':['same source/profile/resource/pid identity','anonymous health is not authenticated acceptance','separate owner MCP/photo consent/card/withdraw acceptance']},
            {'id':'stop','effect':'future-explicit-approval','requirements':['recheck exact unit/paths/process identity','stop only this unit','preserve state and all unrelated services']},
            {'id':'rollback','effect':'future-explicit-approval','requirements':['fresh installation rollback means stop new candidate only','never restore old DB or overwrite source/config automatically','preserve private state/logs for reviewed cleanup','recovery copies stay quarantined']}
        ],
        'blockers':['operator lifecycle implementation and interruption/identity tests',
                    'measured capacity/resource/timeout/disk budget acceptance',
                    'fresh separately approved VPS preflight/loopback/HTTPS acceptance']}
    plan['plan_sha256']=sha256(json.dumps(plan,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return plan


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',required=True);p.add_argument('--source-sha',required=True)
    p.add_argument('--lock-sha256',required=True);p.add_argument('--resource',required=True)
    p.add_argument('--observations',required=True)
    a=p.parse_args()
    path=Path(a.observations)
    if path.stat().st_size>16384:raise PlanError('operator_invalid_observations')
    # No secret-bearing JSON should be provided; unknown keys fail closed.
    def pairs(items):
        result={}
        for k,v in items:
            if k in result:raise PlanError('operator_invalid_observations')
            result[k]=v
        return result
    observations=json.loads(path.read_text(),object_pairs_hook=pairs)
    print(json.dumps(build_plan(a.bundle,a.source_sha,a.lock_sha256,a.resource,observations),sort_keys=True))


if __name__=='__main__':main()
