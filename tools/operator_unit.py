"""Read-only fixed unit renderer. Not a root installer or capacity acceptance."""
import argparse
from pathlib import Path
import re
import runpy

ROOT=Path(__file__).resolve().parents[1]
UNIT='mcp-rooms-candidate.service'
USER='mcp-rooms-candidate'
BASE='/opt/'+USER
STATE='/var/lib/'+USER


def render(source,resource,persistent=False):
    if type(source) is not str or not re.fullmatch('[0-9a-f]{40}',source):
        raise ValueError('unit_invalid_source')
    if type(persistent) is not bool:
        raise ValueError('unit_invalid_mode')
    resource=runpy.run_path(str(ROOT/'tools/operator_plan.py'))['_resource'](resource)
    release=BASE+'/releases/'+source
    if persistent:
        # Opt-in long-lived rendering: no runtime ceiling and a bounded restart policy.
        # Rendering still grants no install/enable/start authority.
        policy='Restart=on-failure\nRestartSec=5s\n'
        install='\n[Install]\nWantedBy=multi-user.target\n'
        mode='persistent (requested; enable still requires separate approval)'
    else:
        policy='Restart=no\nRuntimeMaxSec=2h\n'
        install=''
        mode='transient review unit (accepted TEST shape)'
    # Values are review ceilings, not measured host capacity.
    return f"""# Review candidate only; no install/enable authorization.
# Mode: {mode}
# Source: {source}; capacity acceptance remains pending.
[Unit]
Description=MCP Rooms isolated owner-first candidate
After=network.target

[Service]
Type=exec
User={USER}
Group={USER}
WorkingDirectory={release}
ExecStart={release}/venv/bin/python -I -m mcp_rooms.test_candidate serve --state {STATE}/owner-first --resource {resource}
Environment=PATH=/usr/bin:/bin LANG=C.UTF-8 PYTHONUTF8=1 HOME={STATE}
UMask=0077
KillMode=control-group
SendSIGKILL=yes
TimeoutStartSec=30s
TimeoutStopSec=10s
{policy}CPUAccounting=yes
MemoryAccounting=yes
TasksAccounting=yes
CPUQuota=100%
MemoryMax=1G
MemorySwapMax=0
TasksMax=64
LimitNOFILE=1024
NoNewPrivileges=yes
CapabilityBoundingSet=
AmbientCapabilities=
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths={STATE}
ReadOnlyPaths={BASE}
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
RestrictRealtime=yes
LockPersonality=yes
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
StandardInput=null
StandardOutput=null
StandardError=null
{install}"""


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-sha',required=True);p.add_argument('--resource',required=True)
    p.add_argument('--persistent',action='store_true',
        help='render the opt-in long-lived unit; still grants no install/enable/start authority')
    a=p.parse_args();print(render(a.source_sha,a.resource,a.persistent),end='')


if __name__=='__main__':main()
