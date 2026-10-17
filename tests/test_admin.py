import json
from mcp_rooms.admin import main
from mcp_rooms.identity import IdentityStore
from mcp_rooms.store import RoomStore


def test_cli_secrets_only_private_file_and_failed_delivery_revokes(tmp_path, capsys):
    path = tmp_path / 'rooms.db'; resource = 'https://rooms.example/mcp'
    args = ['--db', str(path), '--resource', resource]
    assert main(args + ['create-user', '--name', 'Example']) == 0
    uid = json.loads(capsys.readouterr().out)['user_id']
    output = tmp_path / 'secret'
    assert main(args + ['issue-token', '--user', uid, '--output', str(output)]) == 0
    report = capsys.readouterr().out
    secret = output.read_text().strip()
    assert secret not in report and 'rm1_' not in report
    assert output.stat().st_mode & 0o777 == 0o600
    auth = IdentityStore(RoomStore(path), resource)
    assert auth.authenticate(secret).user_id == uid
    assert main(args + ['issue-token', '--user', uid, '--output', str(output)]) == 1
    assert 'rm1_' not in capsys.readouterr().out
    with auth.store._db() as db:
        assert db.execute('SELECT COUNT(*) FROM credentials WHERE revoked=1').fetchone()[0] == 1
    cid = json.loads(report)['credential_id']
    assert main(args + ['revoke-token', '--credential', cid]) == 0
    assert auth.authenticate(secret) is None
