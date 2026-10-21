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


def render(source,resource):
    if type(source) is not str or not re.fullmatch('[0-9a-f]{40}',source):
        raise ValueError('unit_invalid_source')
    resource=runpy.run_path(str(ROOT/'tools/operator_plan.py'))['_resource'](resource)
    release=BASE+'/releases/'+source
    # Values are review ceilings, not measured host capacity. No autostart target.
    return f"""# Review candidate only; no install/enable authorization.
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
Restart=no
KillMode=control-group
SendSIGKILL=yes
TimeoutStartSec=30s
TimeoutStopSec=10s
RuntimeMaxSec=2h
CPUAccounting=yes
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
"""


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-sha',required=True);p.add_argument('--resource',required=True)
    a=p.parse_args();print(render(a.source_sha,a.resource),end='')


if __name__=='__main__':main()
