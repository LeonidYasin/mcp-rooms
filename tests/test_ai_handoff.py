"""Repository continuity contract, executed in CI alongside runtime tests."""
from pathlib import Path
import json
import runpy
import shutil
import pytest

ROOT=Path(__file__).resolve().parents[1]
validate=runpy.run_path(str(ROOT/'tools/check_handoff.py'))['validate']


def test_real_repository_handoff():
    result=validate(ROOT)
    assert result['current_slice']!=result['next_task']
    assert result['stage'] in {'SOURCE','CI'}


@pytest.mark.parametrize('change',['sha','stage','missing_source','missing_evidence','self_next','runtime_claim'])
def test_invalid_handoff_fails_closed(tmp_path,change):
    # Only the explicit static document/code files referenced by the validator.
    state=json.loads((ROOT/'docs/work-state.json').read_text())
    files=['docs/work-state.json','docs/project-status.json','README.md','AGENTS.md']
    files+=state['read_next']+[state['accepted']['evidence'],state['next_task']['contract']]
    files+=[state['current_slice'][k] for k in ('contract','source','tests')]
    for name in set(files):
        dest=tmp_path/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    if change=='sha':state['accepted']['source_sha']='not-a-sha'
    if change=='stage':state['current_slice']['stage']='PROD'
    if change=='missing_source':state['current_slice']['source']='missing.py'
    if change=='missing_evidence':state['accepted']['evidence']='missing.md'
    if change=='self_next':state['next_task']['id']=state['current_slice']['id']
    if change=='runtime_claim':state['runtime_last_known']['not_a_current_probe']=False
    (tmp_path/'docs/work-state.json').write_text(json.dumps(state))
    with pytest.raises(AssertionError):validate(tmp_path)
