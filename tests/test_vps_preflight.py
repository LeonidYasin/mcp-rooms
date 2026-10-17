"""Pure parser / mocked preflight. Never inspect a real VPS or run systemctl here."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('vps_preflight', Path(__file__).parents[1] / 'deploy/vps_preflight.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


def test_ss_parser_ipv4_ipv6_and_no_secret_output():
    raw = 'LISTEN 0 128 127.0.0.1:3002 0.0.0.0:*\nLISTEN 0 128 [::]:8765 [::]:*\nLISTEN 0 128 *:443 *:*\n'
    assert module.listeners(raw) == {3002, 8765, 443}


def test_preflight_stops_before_commands_if_not_root(monkeypatch, capsys):
    monkeypatch.setattr(module.os, 'geteuid', lambda: 1000)
    def forbidden(*args): raise AssertionError('must not inspect services')
    monkeypatch.setattr(module, 'command', forbidden)
    assert module.main() == 1
    assert 'operator_root_console_required' in capsys.readouterr().out
