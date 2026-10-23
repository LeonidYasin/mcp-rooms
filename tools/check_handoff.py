"""Static repository handoff integrity; CI only, no application imports/network."""
import json
from pathlib import Path
import re


def validate(root):
    def file(value):
        assert isinstance(value,str) and value and not Path(value).is_absolute()
        p=root/value
        assert '..' not in Path(value).parts and p.is_file() and not p.is_symlink(), value
        return p
    state=json.loads(file('docs/work-state.json').read_text())
    assert state['schema']==1
    assert state['repository']=='LeonidYasin/mcp-rooms'
    assert state['branch']=='feat/standalone-identity' and state['pull_request']==1
    accepted=state['accepted']
    assert re.fullmatch('[0-9a-f]{40}',accepted['source_sha'])
    assert accepted['kind']=='CI_NOT_DEPLOYMENT'
    assert type(accepted['python312_passed']) is int and accepted['python312_passed']>0
    assert accepted['source_sha'] in file(accepted['evidence']).read_text()
    assert accepted['source_sha'] in file('README.md').read_text()
    if accepted.get('vps_test_evidence'):
        assert accepted['source_sha'] in file(accepted['vps_test_evidence']).read_text()
    current=state['current_slice']
    assert current['stage'] in {'SOURCE','CI','TEST'}
    for key in ('contract','source','tests'):file(current[key])
    registry=json.loads(file('docs/project-status.json').read_text())
    component=[n for n in registry['components'] if n['source']==current['source']]
    assert len(component)==1 and component[0]['stage']==current['stage']
    assert component[0]['doc']==current['contract']
    if current['stage']=='CI':
        assert current['evidence']==accepted['evidence']==component[0]['evidence']
    elif current['stage']=='TEST':
        assert accepted.get('vps_test_evidence')
        assert current['evidence']==component[0]['evidence']
        file(current['evidence'])
    else:
        assert current['evidence'] is None and component[0]['evidence'] is None
    task=state['next_task']
    assert task['id']!=current['id'] and len(task['acceptance'])>=4
    assert all(isinstance(v,str) and len(v)>20 for v in task['acceptance'])
    file(task['contract'])
    for value in state['read_next']:file(value)
    assert state['runtime_last_known']['not_a_current_probe'] is True
    assert state['verification']['runtime'] in {
        'GitHub Actions only',
        'GitHub Actions plus separately authorized VPS loopback TEST; no HTTPS or production',
    }
    agents=file('AGENTS.md').read_text()
    assert 'docs/ai-handoff.md' in agents and 'docs/work-state.json' in agents
    assert 'special password' in agents and 'expected-head CAS' in agents
    return {'accepted_source':accepted['source_sha'],'current_slice':current['id'],
            'stage':current['stage'],'next_task':task['id']}


if __name__=='__main__':
    result=validate(Path(__file__).resolve().parents[1])
    print('HANDOFF QA PASS: '+json.dumps(result,sort_keys=True))
