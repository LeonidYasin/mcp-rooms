"""Guard tests for the privileged persistent-unit CI harness. No host effects."""
from pathlib import Path
import runpy
import pytest

ROOT=Path(__file__).resolve().parents[1]
m=runpy.run_path(str(ROOT/'tools/ci_persistent_unit.py'))


def test_refuses_outside_isolated_actions(monkeypatch):
    monkeypatch.delenv('GITHUB_ACTIONS',raising=False)
    with pytest.raises(RuntimeError,match='isolated_root_actions_only'):m['main']()


def test_refuses_when_actions_flag_is_not_exactly_true(monkeypatch):
    monkeypatch.setenv('GITHUB_ACTIONS','1')
    with pytest.raises(RuntimeError,match='isolated_root_actions_only'):m['main']()


def test_fixture_unit_carries_the_same_policy_as_the_real_unit():
    unit=m['fixture_unit']()
    assert 'Restart=on-failure' in unit and 'RestartSec=1s' in unit
    assert 'RuntimeMaxSec' not in unit
    assert '[Install]\nWantedBy=multi-user.target\n' in unit
    assert 'KillMode=control-group' in unit and 'NoNewPrivileges=yes' in unit


def test_fixed_fixture_names_never_collide_with_the_candidate_unit():
    assert m['NAME']!= 'mcp-rooms-candidate.service'
    assert m['WORK']==Path('/run/mcp-rooms-ci-persistent')
    assert m['UNIT']==Path('/run/systemd/system')/m['NAME']
    assert m['WANTS']==Path('/etc/systemd/system/multi-user.target.wants')/m['NAME']
