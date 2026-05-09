from __future__ import annotations

from harbor.prompt import parse_sentinel, render_worker_prompt


def test_render_includes_id_title_and_description():
    bead = {
        "id": "awt-zmq.1",
        "title": "Scaffold harbor",
        "description": "Read:\n- README\n\nFiles:\n- harbor/x.py\n\nVerify:\n- pytest",
    }
    text = render_worker_prompt(bead)
    assert "awt-zmq.1" in text
    assert "Scaffold harbor" in text
    assert "harbor/x.py" in text
    assert "HARBOR-DONE" in text


def test_render_handles_missing_description():
    text = render_worker_prompt({"id": "awt-z.x", "title": "t"})
    assert "(no description)" in text
    assert "HARBOR-DONE" in text


def test_render_mentions_classification_options():
    text = render_worker_prompt({"id": "b", "title": "t", "description": "d"})
    for c in ("clarify", "env", "contract", "scope"):
        assert c in text


def test_render_instructs_successful_workers_to_commit_with_epic_prefix():
    bead = {
        "id": "awt-zmq.1",
        "title": "Implement something",
        "description": "Read:\n- README\n\nFiles:\n- harbor/x.py\n\nVerify:\n- pytest",
    }
    text = render_worker_prompt(bead)
    assert "Before emitting `status=ok`, commit" in text
    assert "subject starts exactly `awt-zmq:`" in text
    assert 'git commit -m "awt-zmq: <short summary>"' in text
    assert "Do NOT commit when emitting `status=blocked`" in text


def test_parse_sentinel_ok():
    out = "doing things\n\nHARBOR-DONE: awt-zmq.1 status=ok classification=none\n"
    assert parse_sentinel(out, "awt-zmq.1") == ("ok", "none")


def test_parse_sentinel_blocked_with_classification():
    out = "stuff\nHARBOR-DONE: b-9 status=blocked classification=contract\n"
    assert parse_sentinel(out, "b-9") == ("blocked", "contract")


def test_parse_sentinel_uses_last_match():
    out = (
        "HARBOR-DONE: id status=ok classification=none\n"
        "false alarm, retrying\n"
        "HARBOR-DONE: id status=blocked classification=env\n"
    )
    assert parse_sentinel(out, "id") == ("blocked", "env")


def test_parse_sentinel_returns_none_when_id_mismatches():
    out = "HARBOR-DONE: other-id status=ok classification=none\n"
    assert parse_sentinel(out, "my-id") is None


def test_parse_sentinel_returns_none_for_invalid_status():
    out = "HARBOR-DONE: id status=maybe classification=clarify\n"
    assert parse_sentinel(out, "id") is None


def test_parse_sentinel_returns_none_when_absent():
    assert parse_sentinel("just some output\n", "id") is None
