"""Operator-run read-only VPS preflight. No install, auth DB, Caddy config, or restart."""
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys

PORT = 8765
NEW_USER = 'mcp-rooms-test'
NEW_UNIT = 'mcp-rooms-test.service'
UNITS = ('mcp-server.service', 'mcp-test.service', 'caddy.service')


def command(args):
    return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, timeout=15).strip()


def listeners(raw):
    result = set()
    for line in raw.splitlines():
        parts = line.split()
        # ss -H -ltn: State Recv-Q Send-Q Local-Address:Port Peer-Address:Port
        if len(parts) >= 5:
            value = parts[3].rsplit(':', 1)[-1]
            if value.isdigit(): result.add(int(value))
    return result


def service(unit):
    raw = command(['systemctl', 'show', unit, '--no-pager',
                   '--property=LoadState,ActiveState,SubState,MainPID,User,WorkingDirectory'])
    return dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)


def main():
    if os.geteuid() != 0:
        print(json.dumps({'result': 'STOP', 'reason': 'operator_root_console_required'})); return 1
    try:
        services = {unit: service(unit) for unit in UNITS}
        proposed = service(NEW_UNIT)
        used = listeners(command(['ss', '-H', '-ltn']))
        disk = shutil.disk_usage('/home')
        memory_kib = None
        for line in Path('/proc/meminfo').read_text().splitlines():
            if line.startswith('MemAvailable:'): memory_kib = int(line.split()[1])
        try:
            account = pwd.getpwnam(NEW_USER)
            account_info = {'exists': True, 'uid': account.pw_uid, 'home': account.pw_dir}
        except KeyError:
            account_info = {'exists': False}
        paths = {path: Path(path).exists() or Path(path).is_symlink() for path in
                 ('/home/mcp-rooms-test', '/etc/systemd/system/mcp-rooms-test.service')}
        blockers = []
        if not (3, 10) <= sys.version_info[:2] <= (3, 13): blockers.append('python_outside_ci_matrix')
        if PORT in used: blockers.append('candidate_port_in_use')
        if proposed.get('LoadState') != 'not-found': blockers.append('candidate_unit_already_exists')
        if account_info['exists'] or any(paths.values()): blockers.append('candidate_identity_or_path_exists_review_required')
        if disk.free < 2 * 1024**3 or disk.free / disk.total < .10: blockers.append('insufficient_disk_reserve')
        if memory_kib is None or memory_kib < 384 * 1024: blockers.append('insufficient_memory_reserve')
        if any(p.get('ActiveState') != 'active' for p in services.values()): blockers.append('existing_service_not_active')
        print(json.dumps({'result': 'ROOMS VPS PREFLIGHT', 'python': sys.version.split()[0],
            'services': services, 'candidate_unit': proposed, 'candidate_port': PORT,
            'candidate_port_free': PORT not in used, 'candidate_user': account_info,
            'existing_candidate_paths': paths, 'disk_free_mib': disk.free // 1024**2,
            'memory_available_mib': memory_kib // 1024 if memory_kib is not None else None,
            'blockers': blockers, 'ready_for_reviewed_loopback_install': not blockers,
            'public_route_authorized_by_this_check': False,
            'config_changed': False, 'services_restarted': False, 'packages_installed': False,
            'database_opened': False, 'credentials_read': False}, ensure_ascii=False))
        return 0 if not blockers else 2
    except Exception:
        print(json.dumps({'result': 'STOP', 'reason': 'preflight_failed_no_details_disclosed',
                          'config_changed': False, 'services_restarted': False}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
