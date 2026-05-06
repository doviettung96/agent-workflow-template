"""Tests for harbor.mail. We exercise it against a real on-disk fake repo so the
underlying agent_mail module's lock + JSON files actually get written. Each
test gets its own tmp_path so state is isolated."""
from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

# Path to the real shared script we want to wrap
TEMPLATE_ROOT = Path(__file__).resolve().parents[2]
SHARED_AGENT_MAIL = TEMPLATE_ROOT / "scripts" / "shared" / "agent_mail.py"


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """A throwaway git repo with scripts/shared/agent_mail.py copied in."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    # An empty initial commit so git-common-dir resolves cleanly.
    (repo / "README.md").write_text("x")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)

    shared = repo / "scripts" / "shared"
    shared.mkdir(parents=True)
    shutil.copy(SHARED_AGENT_MAIL, shared / "agent_mail.py")
    return repo


def _reset_mail_module():
    """Force harbor.mail to re-import agent_mail from the new fake_repo path."""
    import harbor.mail as mail_mod
    mail_mod._AGENT_MAIL_MODULE = None
    import sys
    sys.modules.pop("agent_mail", None)


def test_register_and_unregister(fake_repo: Path):
    _reset_mail_module()
    from harbor.mail import Mail

    m = Mail(fake_repo)
    out = m.register(name="harbor/main", role="coordinator", epic_id="epic-1")
    assert out["ok"] is True
    assert out["agent"]["name"] == "harbor/main"
    assert out["agent"]["epic_id"] == "epic-1"

    agents_path = fake_repo / ".git" / "agent-swarm" / "agents.json"
    assert agents_path.exists()
    agents = json.loads(agents_path.read_text(encoding="utf-8"))
    assert any(a["name"] == "harbor/main" for a in agents)

    m.unregister("harbor/main")
    agents = json.loads(agents_path.read_text(encoding="utf-8"))
    assert not any(a["name"] == "harbor/main" for a in agents)


def test_acquire_epic_lock_and_conflict(fake_repo: Path):
    _reset_mail_module()
    from harbor.mail import Mail

    m = Mail(fake_repo)
    res = m.acquire_epic(epic_id="epic-1", owner="harbor/A")
    assert res["lock"]["epic_id"] == "epic-1"
    assert res["lock"]["owner"] == "harbor/A"

    # Same owner can re-acquire safely
    m.acquire_epic(epic_id="epic-1", owner="harbor/A")

    # Different owner conflicts
    with pytest.raises(Exception) as ei:
        m.acquire_epic(epic_id="epic-1", owner="harbor/B")
    assert "already locked" in str(ei.value).lower()

    m.release_epic(epic_id="epic-1", owner="harbor/A")


def test_reserve_then_release(fake_repo: Path):
    _reset_mail_module()
    from harbor.mail import Mail

    m = Mail(fake_repo)
    m.reserve(owner="harbor/B", paths=["src/a.py", "src/b.py"], epic_id="e1", bead_id="b1")
    res_path = fake_repo / ".git" / "agent-swarm" / "reservations.json"
    data = json.loads(res_path.read_text(encoding="utf-8"))
    assert {r["path"] for r in data} == {"src/a.py", "src/b.py"}

    m.release_reservations(owner="harbor/B", bead_id="b1")
    data = json.loads(res_path.read_text(encoding="utf-8"))
    assert data == []


def test_reserve_conflict_when_overlapping_owner(fake_repo: Path):
    _reset_mail_module()
    from harbor.mail import Mail

    m = Mail(fake_repo)
    m.reserve(owner="harbor/A", paths=["src/x.py"], epic_id="e", bead_id="b1")
    with pytest.raises(Exception):
        m.reserve(owner="harbor/B", paths=["src/x.py"], epic_id="e", bead_id="b2")


def test_post_writes_to_thread(fake_repo: Path):
    _reset_mail_module()
    from harbor.mail import Mail

    m = Mail(fake_repo)
    m.post(
        thread="bead/awt-1",
        sender="harbor/main",
        body=json.dumps({"hello": "world"}),
        message_type="started",
        epic_id="epic-1",
        bead_id="awt-1",
    )
    thread_path = fake_repo / ".git" / "agent-swarm" / "threads" / "bead_awt-1.jsonl"
    assert thread_path.exists()
    line = thread_path.read_text(encoding="utf-8").strip().splitlines()[0]
    rec = json.loads(line)
    assert rec["thread"] == "bead/awt-1"
    assert rec["sender"] == "harbor/main"
